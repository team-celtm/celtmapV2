import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

# Mocking enough of the environment to test MCQService
from app.repositories.assessment_repository import AssessmentRepository
from app.services.mcq_service import MCQService

load_dotenv()

async def verify_mcq():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)
    
    repo = AssessmentRepository(supabase)
    # We need to mock dependencies of MCQService if it uses them in get_placement_questions
    # Passing None for services we don't plan to trigger (events, etc)
    svc = MCQService(repository=repo, event_service=None)
    
    print("Fetching placement questions...")
    try:
        questions = await svc.get_placement_questions()
        print(f"SUCCESS: Found {len(questions)} questions.")
        
        if questions:
            for i, q in enumerate(questions[:3]):
                print(f"\nQuestion {i+1}: {q['question_text']}")
                print(f"Category: {q['category']}")
                print(f"Options: {len(q['options'])}")
                for opt in q['options']:
                    print(f"  [{opt['id']}] {opt['option_text']}")
        else:
            print("WARNING: No questions returned.")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_mcq())
