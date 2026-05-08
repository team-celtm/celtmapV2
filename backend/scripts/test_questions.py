import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

async def test_get_questions():
    from app.config.settings import get_settings
    from app.integrations.supabase import get_supabase_client
    from app.repositories.assessment_repository import AssessmentRepository
    from app.services.mcq_service import MCQService
    from app.services.domain_event_service import DomainEventService
    
    settings = get_settings()
    client = get_supabase_client(settings)
    repo = AssessmentRepository(client)
    event_service = DomainEventService(client)
    service = MCQService(repo, event_service)
    
    subjects = ["Machine Learning", "Cloud Computing", "Algorithms"]
    
    for subject in subjects:
        questions = await service.get_questions(
            category=subject,
            difficulty=None,
            limit=20, # Requesting 20 to test the 10-limit cap
        )
        print(f"\nSubject: {subject}")
        print(f"Number of questions returned: {len(questions)}")
        if questions:
            print(f"First question: {questions[0]['question_text'][:100]}...")
            print(f"Number of options: {len(questions[0]['options'])}")

if __name__ == "__main__":
    asyncio.run(test_get_questions())
