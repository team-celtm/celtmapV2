import asyncio
import unittest
from collections import Counter

from app import career_roles
from app.ai import resolve_career_aim, suggest_career_aims
from app.main import (
    _canonical_career_role,
    _subject_card_payload,
    _subjects_needed_for_role,
    career_role_options,
    roadmap_from_phase_details,
    roadmap_phase_details,
    role_specific_readiness,
)
from app.settings import Settings


class CareerRoleTests(unittest.TestCase):
    def test_every_catalog_alias_resolves_to_canonical_role(self) -> None:
        for item in career_roles.CAREER_ROLE_CATALOG:
            expected = item["label"]
            candidates = [expected, *item.get("aliases", [])]
            for candidate in candidates:
                with self.subTest(candidate=candidate):
                    self.assertEqual(career_roles.canonical_career_role(candidate), expected)

    def test_every_catalog_role_has_subjects_and_adjacent_paths(self) -> None:
        for item in career_roles.CAREER_ROLE_CATALOG:
            with self.subTest(role=item["label"]):
                role_key, role_label, subjects = career_roles.subjects_for_role(item["label"])

                self.assertEqual(role_key, item["profile_key"])
                self.assertEqual(role_label, item["label"])
                self.assertGreaterEqual(len(subjects), 3)
                self.assertGreaterEqual(len(career_roles.adjacent_fits_for_role(item["label"], role_key)), 2)

    def test_ca_alias_maps_to_chartered_accountant(self) -> None:
        self.assertEqual(_canonical_career_role("CA"), "Chartered Accountant")

        fit = role_specific_readiness(
            "CA",
            {
                "readiness": 0,
                "domain_breakdown": {},
                "readiness_components": [],
                "resume": None,
            },
        )

        self.assertEqual(fit["role_profile_key"], "chartered_accounting")
        self.assertEqual(fit["role_profile"], "Chartered Accounting")

    def test_custom_role_is_allowed_as_typeable_career_aim(self) -> None:
        self.assertEqual(_canonical_career_role("space psychologist"), "Space Psychologist")

        role_key, role_label, subjects = _subjects_needed_for_role("space psychologist")
        self.assertEqual(role_key, "custom")
        self.assertEqual(role_label, "Space Psychologist")
        self.assertGreaterEqual(len(subjects), 3)

    def test_resolver_fallback_maps_ca_to_chartered_accountant(self) -> None:
        settings = Settings(OPENAI_API_KEY="")
        resolved = asyncio.run(resolve_career_aim(settings, "CA", career_roles.career_role_options()))

        self.assertEqual(resolved["normalized_role"], "Chartered Accountant")
        self.assertEqual(resolved["matched_catalog_role"], "Chartered Accountant")
        self.assertTrue(resolved["is_supported_catalog"])

    def test_ai_dropdown_suggestions_keep_ambiguous_ca_options(self) -> None:
        settings = Settings(OPENAI_API_KEY="")
        suggestions = asyncio.run(suggest_career_aims(settings, "CA", career_roles.career_role_options()))
        labels = [item["label"] for item in suggestions]

        self.assertIn("Chartered Accountant", labels)
        self.assertIn("Career Analyst", labels)
        self.assertNotIn("Full Stack Developer", labels[:2])

    def test_accounting_role_uses_accounting_subjects_and_roadmap(self) -> None:
        role_key, role_label, subjects = _subjects_needed_for_role("CA")

        self.assertEqual(role_key, "chartered_accounting")
        self.assertEqual(role_label, "Chartered Accountant")
        self.assertIn("Accounting", subjects)
        self.assertIn("Taxation", subjects)

        fit = role_specific_readiness(
            "Chartered Accountant",
            {
                "readiness": 0,
                "domain_breakdown": {},
                "readiness_components": [],
                "resume": None,
            },
        )
        roadmap = roadmap_from_phase_details(roadmap_phase_details("Chartered Accountant", fit, ["Accounting"]))
        flattened = " ".join(item for items in roadmap.values() for item in items)

        self.assertIn("Financial statement analysis", flattened)
        self.assertNotIn("Build and explain one API", flattened)

        card = _subject_card_payload(
            "Accounting",
            "Chartered Accountant",
            {},
            {},
            Counter(),
            Counter(),
            Counter(),
        )

        self.assertFalse(card["is_available"])
        self.assertEqual(card["source"], "Coming soon")
        self.assertIn("live questions are still being prepared", card["description"])

    def test_career_role_options_include_chartered_accountant(self) -> None:
        options = career_role_options()
        labels = {item["label"] for item in options}

        self.assertIn("Chartered Accountant", labels)
        self.assertGreaterEqual(len(options), 1000)

    def test_preloaded_career_options_include_ambiguous_abbreviations(self) -> None:
        options = career_role_options()
        ca_labels = {
            item["label"]
            for item in options
            if "CA" in [str(alias).upper().replace(".", "") for alias in item.get("aliases", [])]
        }

        self.assertIn("Chartered Accountant", ca_labels)
        self.assertIn("Career Analyst", ca_labels)


if __name__ == "__main__":
    unittest.main()
