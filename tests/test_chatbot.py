import pytest
from chatbot import AIOpsChatbot

def test_chatbot_initialization():
    """
    Test if the AIOpsChatbot instance is created successfully.
    """
    try:
        bot = AIOpsChatbot()
        assert bot is not None
        assert isinstance(bot, AIOpsChatbot)
    except Exception as e:
        pytest.fail(f"AIOpsChatbot initialization failed with an exception: {e}")
