import asyncio
import os
import sys

# Add current directory to path so 'app' is found correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.services.written_assessment_service import WrittenAssessmentService
from app.repositories.assessment_repository import AssessmentRepository

async def verify():
    # Attempt to initialize service with a real DB session
    # We use a context manager to ensure DB is initialized
    from app.core import config
    
    print("Verifying WrittenAssessmentService question discovery...")
    repo = AssessmentRepository()
    service = WrittenAssessmentService(repo)
    
    # Test case 1: Generic search (e.g. Python)
    print("\nTesting keyword: 'Python'")
    prompt = await service._resolve_prompt(search_query="Python")
    print(f"Discovered prompt: {prompt[:100]}...")
    
    # Test case 2: No match search (should pull from pool)
    print("\nTesting no-match keyword: 'NonExistentSkillSearch'")
    prompt = await service._resolve_prompt(search_query="NonExistentSkillSearch")
    print(f"Discovered prompt: {prompt[:100]}...")
    
    if "This is a test prompt" in prompt:
        print("\nFAILURE: System fell back to test prompt.")
    else:
        print("\nSUCCESS: System pulled a real question from the DB.")

if __name__ == "__main__":
    asyncio.run(verify())
