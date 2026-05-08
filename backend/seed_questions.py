import asyncio
import uuid
from datetime import datetime, UTC
from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.services.fallback_placement_questions import FALLBACK_QUESTIONS

async def seed_questions():
    settings = get_settings()
    supabase = get_supabase_client(settings)
    
    print(f"Starting seed of {len(FALLBACK_QUESTIONS)} questions...")
    
    # Fetch existing questions to avoid duplicates
    existing_res = supabase.table("questions").select("id, question_text").execute()
    existing_texts = {q["question_text"] for q in existing_res.data}
    
    # Fetch available skills for FK reference
    skills_res = supabase.table("skills").select("id, name").execute()
    skill_map = {s["name"].lower(): s["id"] for s in skills_res.data}
    default_skill_id = skills_res.data[0]["id"] if skills_res.data else str(uuid.uuid4())
    
    # Fetch available subskills for FK reference
    subskills_res = supabase.table("subskills").select("id, name").execute()
    subskill_map = {ss["name"].lower(): ss["id"] for ss in subskills_res.data}
    default_subskill_id = subskills_res.data[0]["id"] if subskills_res.data else str(uuid.uuid4())
    
    new_questions = []
    for q in FALLBACK_QUESTIONS:
        if q["question_text"] not in existing_texts:
            # Try to find a matching skill or fallback to default
            s_id = skill_map.get(q["category"].lower(), default_skill_id)
            ss_id = subskill_map.get(q["category"].lower(), default_subskill_id)
            
            new_questions.append({
                "question_text": q["question_text"],
                "question_text_normalized": q["question_text"].strip().lower(),
                "category": q["category"],
                "difficulty": q.get("difficulty", "medium"),
                "question_type": "mcq",
                "skill_id": s_id,
                "subskill_id": ss_id,
                "is_active": True,
            })
    
    if new_questions:
        print(f"Inserting {len(new_questions)} new questions...")
        q_response = supabase.table("questions").insert(new_questions).execute()
        db_questions = q_response.data
    else:
        print("No new questions to insert.")
        db_questions = existing_res.data

    # Fetch all questions now for option mapping
    full_db_res = supabase.table("questions").select("id, question_text").execute()
    question_map = {q["question_text"]: q["id"] for q in full_db_res.data}
    
    # Options
    existing_options_res = supabase.table("question_options").select("question_id, option_text").execute()
    existing_options = {(opt["question_id"], opt["option_text"]) for opt in existing_options_res.data}
    
    options_payload = []
    for q in FALLBACK_QUESTIONS:
        q_id = question_map.get(q["question_text"])
        if not q_id: continue
        
        for opt in q["options"]:
            if (q_id, opt["option_text"]) not in existing_options:
                options_payload.append({
                    "question_id": q_id,
                    "option_text": opt["option_text"],
                    "is_correct": opt["is_correct"],
                    "option_key": opt["id"][-1] # Fallback key from ID suffix
                })
    
    if options_payload:
        print(f"Inserting {len(options_payload)} new options...")
        supabase.table("question_options").insert(options_payload).execute()
    
    print("Seed completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_questions())
