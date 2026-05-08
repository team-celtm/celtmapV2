import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

def get_uuid(integer_id):
    try:
        if pd.isna(integer_id):
            return None
        val = int(integer_id)
        return f"00000000-0000-0000-0000-{val:012d}"
    except (ValueError, TypeError):
        return None

def main():
    load_dotenv()
    db_string = os.getenv("SUPABASE_DB_CONNECTION_STRING")
    if not db_string:
        print("Missing SUPABASE_DB_CONNECTION_STRING in .env")
        return

    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "CELTMIND")
    skills_csv = os.path.join(data_dir, "skills_master.csv")
    
    if not os.path.exists(skills_csv):
        print(f"Skipping skills, file not found: {skills_csv}")
        return

    df_skills = pd.read_csv(skills_csv)
    unique_skills = df_skills.drop_duplicates(subset=['skill_id'])
    
    try:
        conn = psycopg2.connect(db_string)
        conn.autocommit = True
        cursor = conn.cursor()
    except Exception as e:
        print(f"DB connection failed: {e}")
        return

    print("Inserting skills...")
    inserted_skill_ids = set()
    for idx, row in unique_skills.iterrows():
        sid = get_uuid(row['skill_id'])
        if sid:
            cursor.execute('''
                INSERT INTO public.skills (id, name, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, id = EXCLUDED.id
                RETURNING id;
            ''', (sid, str(row['skill_name']).strip(), str(row['skill_definition']) if pd.notna(row['skill_definition']) else None))
            res = cursor.fetchone()
            if res:
                inserted_skill_ids.add(res[0])

    print("Inserting subskills...")
    inserted_subskill_ids = set()
    unique_subskills = df_skills.drop_duplicates(subset=['subskill_id'])
    for idx, row in unique_subskills.iterrows():
        susid = get_uuid(row['subskill_id'])
        sid = get_uuid(row['skill_id'])
        if susid and sid and sid in inserted_skill_ids:
            cursor.execute('''
                INSERT INTO public.subskills (id, skill_id, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                RETURNING id;
            ''', (susid, sid, str(row['subskill_name']).strip()))
            res = cursor.fetchone()
            if res:
                inserted_subskill_ids.add(res[0])
            else:
                # If it was already there (DO NOTHING), we still need it in the set
                inserted_subskill_ids.add(susid)

    print("Inserting questions...")
    df_q = pd.read_csv(os.path.join(data_dir, "questions.csv"))
    df_q_dedup = df_q.drop_duplicates(subset=['question_text'], keep='first')
    
    valid_q_ids = set()
    for idx, row in df_q_dedup.iterrows():
        try:
            sk_id = row['skill_id'] if pd.notna(row['skill_id']) and row['skill_id'] != '' else None
            subsk_id = row['subskill_id'] if pd.notna(row['subskill_id']) and row['subskill_id'] != '' else None
            
            # Verify foreign keys
            if sk_id and sk_id not in inserted_skill_ids:
                sk_id = None
            if subsk_id and subsk_id not in inserted_subskill_ids:
                subsk_id = None

            cursor.execute('''
                INSERT INTO public.questions (id, question_text, question_type, difficulty, subject_id, skill_id, subskill_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
            ''', (
                row['id'], 
                str(row['question_text']), 
                str(row['question_type']).lower(), 
                str(row['difficulty']).lower() if pd.notna(row['difficulty']) else None, 
                str(row['subject_id']) if pd.notna(row['subject_id']) else None, 
                sk_id, 
                subsk_id, 
                bool(row['is_active']), 
                row['created_at']
            ))
            valid_q_ids.add(row['id'])
        except Exception as e:
            print(f"Error inserting question {row['id']}: {e}")

    print("Inserting MCQ...")
    df_mcq = pd.read_csv(os.path.join(data_dir, "mcq_questions.csv"))
    for idx, row in df_mcq.iterrows():
        if row['question_id'] in valid_q_ids:
            try:
                cursor.execute('''
                    INSERT INTO public.mcq_questions (question_id, option_a, option_b, option_c, option_d, correct_option)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (question_id) DO NOTHING;
                ''', (row['question_id'], str(row['option_a']), str(row['option_b']), str(row['option_c']), str(row['option_d']), str(row['correct_option'])))
            except Exception as e:
                print(f"Error MCQ {row['question_id']}: {e}")

    print("Inserting Situational MCQ...")
    df_sit = pd.read_csv(os.path.join(data_dir, "situational_mcq_questions.csv"))
    for idx, row in df_sit.iterrows():
        if row['question_id'] in valid_q_ids:
            try:
                cursor.execute('''
                    INSERT INTO public.situational_mcq_questions (question_id, scenario, option_a, option_b, option_c, option_d, correct_option)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (question_id) DO NOTHING;
                ''', (row['question_id'], str(row['scenario']), str(row['option_a']), str(row['option_b']), str(row['option_c']), str(row['option_d']), str(row['correct_option'])))
            except Exception as e:
                print(f"Error Sit {row['question_id']}: {e}")

    print("Inserting Descriptive...")
    df_desc = pd.read_csv(os.path.join(data_dir, "descriptive_questions.csv"))
    for idx, row in df_desc.iterrows():
        if row['question_id'] in valid_q_ids:
            try:
                rubric = row['evaluation_rubric']
                cursor.execute('''
                    INSERT INTO public.descriptive_questions (question_id, expected_answer, evaluation_rubric)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (question_id) DO NOTHING;
                ''', (row['question_id'], str(row['expected_answer']) if pd.notna(row['expected_answer']) else None, rubric if pd.notna(rubric) else None))
            except Exception as e:
                print(f"Error Desc {row['question_id']}: {e}")

    print("Success! Ingestion Complete.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
