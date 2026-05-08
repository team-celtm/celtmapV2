from __future__ import annotations

from datetime import datetime, timezone

from neo4j import AsyncDriver

from app.core.exceptions import IntegrationError
from app.repositories.skill_repository import SkillRepository


class GraphSyncService:
    def __init__(self, repository: SkillRepository, driver: AsyncDriver | None) -> None:
        self.repository = repository
        self.driver = driver

    async def sync_user(self, user_id: str, event_id: str | None = None) -> None:
        if self.driver is None:
            return
        synced_at = datetime.now(timezone.utc).isoformat()
        user_skills = await self.repository.list_user_skills(user_id)
        roles = await self.repository.list_roles()
        role_requirements = await self.repository.list_role_requirements()

        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (u:User {id: $user_id})
                SET u.last_synced_at = $synced_at,
                    u.last_synced_event_id = coalesce($event_id, u.last_synced_event_id)
                """,
                user_id=user_id,
                synced_at=synced_at,
                event_id=event_id,
            )
            await session.run(
                """
                MATCH (u:User {id: $user_id})-[r:HAS_SKILL]->(:Skill)
                DELETE r
                """,
                user_id=user_id,
            )

            for role in roles:
                await session.run(
                    """
                    MERGE (r:Role {name: $role_name})
                    SET r.description = $description,
                        r.last_synced_at = $synced_at,
                        r.last_synced_event_id = coalesce($event_id, r.last_synced_event_id)
                    """,
                    role_name=role["role_name"],
                    description=role.get("description"),
                    synced_at=synced_at,
                    event_id=event_id,
                )

            for requirement in role_requirements:
                skill_name = requirement["skill_name"]
                await session.run(
                    """
                    MERGE (role:Role {name: $role_name})
                    MERGE (skill:Skill {name: $skill_name})
                    MERGE (skill)-[rel:REQUIRED_FOR]->(role)
                    SET rel.weight = $weight,
                        rel.last_synced_at = $synced_at,
                        rel.last_synced_event_id = coalesce($event_id, rel.last_synced_event_id)
                    """,
                    role_name=requirement["role_name"],
                    skill_name=skill_name,
                    weight=requirement["weight"],
                    synced_at=synced_at,
                    event_id=event_id,
                )
                prerequisite_skill_name = requirement.get("prerequisite_skill_name")
                if prerequisite_skill_name:
                    await session.run(
                        """
                        MERGE (prerequisite:Skill {name: $prerequisite_skill_name})
                        MERGE (skill:Skill {name: $skill_name})
                        MERGE (prerequisite)-[rel:DEPENDS_ON]->(skill)
                        SET rel.last_synced_at = $synced_at,
                            rel.last_synced_event_id = coalesce($event_id, rel.last_synced_event_id)
                        """,
                        prerequisite_skill_name=prerequisite_skill_name,
                        skill_name=skill_name,
                        synced_at=synced_at,
                        event_id=event_id,
                    )

            for skill in user_skills:
                skill_name = skill.get("skill_name") or skill.get("skill_id")
                await session.run(
                    """
                    MERGE (u:User {id: $user_id})
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (u)-[r:HAS_SKILL]->(s)
                    SET r.score = $score,
                        r.last_synced_at = $synced_at,
                        r.last_synced_event_id = coalesce($event_id, r.last_synced_event_id)
                    """,
                    user_id=user_id,
                    skill_name=skill_name,
                    score=skill["proficiency_score"],
                    synced_at=synced_at,
                    event_id=event_id,
                )

    async def healthcheck(self) -> bool:
        if self.driver is None:
            return False
        try:
            async with self.driver.session() as session:
                await session.run("RETURN 1")
        except Exception as exc:
            raise IntegrationError("Neo4j healthcheck failed") from exc
        return True
