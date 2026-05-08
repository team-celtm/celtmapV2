from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.mcq_service import MCQService


@pytest.mark.asyncio
async def test_mcq_randomization_range():
    # Mock repository
    mock_repo = MagicMock()
    mock_repo.get_questions = AsyncMock(return_value=[{"id": f"q{i}", "question_text": "text", "category": "cat", "difficulty": "med"} for i in range(30)])
    mock_repo.get_options_for_questions = AsyncMock(return_value=[])
    
    # Mock event service
    mock_event = MagicMock()
    
    service = MCQService(repository=mock_repo, event_service=mock_event)
    
    # Run 10 times to check range
    for _ in range(10):
        questions = await service.get_questions(category="tech", difficulty="medium", limit=1)
        # The limit parameter should be ignored because of the randint(5, 20) in the service
        assert 5 <= len(questions) <= 20
        print(f"Randomized batch size: {len(questions)}")

@pytest.mark.asyncio
async def test_mcq_scoring_logic():
    mock_repo = MagicMock()
    mock_repo.get_assessment = AsyncMock(return_value={"id": "a1", "category": "tech"})
    # Mock answers: 2 correct, 1 incorrect
    mock_repo.list_user_answers = AsyncMock(return_value=[
        {"is_correct": True, "selected_option_id": "o1"},
        {"is_correct": True, "selected_option_id": "o2"},
        {"is_correct": False, "selected_option_id": "o3"},
    ])
    mock_repo.update_assessment = AsyncMock()
    
    mock_event = MagicMock()
    mock_event.emit = AsyncMock()
    
    service = MCQService(repository=mock_repo, event_service=mock_event)
    
    result = await service.complete_assessment(assessment_id="a1", user_id="u1")
    
    assert result["score"] == 66.67 # (2/3) * 100
    assert result["status"] == "completed"
    assert mock_repo.update_assessment.called
