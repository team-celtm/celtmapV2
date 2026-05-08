import os
import asyncio
from supabase import create_client
from dotenv import load_dotenv
from app.repositories.assessment_repository import AssessmentRepository
from app.services.mcq_service import MCQService
from app.services.domain_event_service import DomainEventService

load_dotenv()

async def verify():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    client = create_client(url, key)
    
    repo = AssessmentRepository(client)
    event_service = DomainEventService(client)
    service = MCQService(repo, event_service)
    
    print("Testing get_placement_questions...")
    try:
        questions = await service.get_placement_questions(role_name="Software Engineer")
        print(f"Successfully fetched {len(questions)} questions.")
        if questions:
            print(f"Sample Question: {questions[0].get('question_text')}")
            print(f"Options Count: {len(questions[0].get('options', []))}")
    except Exception as e:
        print(f"Verification Failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
