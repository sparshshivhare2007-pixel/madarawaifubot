# shivu/modules/helpers.py

import time
from typing import Dict, Optional

# ==============================
#      COOLDOWN SYSTEM
# ==============================

# Global cooldown dictionary
_user_cooldowns: Dict[int, Dict[str, float]] = {}

# Default cooldown times (in seconds)
DEFAULT_COOLDOWN = 30
COMMAND_COOLDOWNS = {
    "guess": 30,
    "spawn": 60,
    "trade": 10,
    "gift": 15,
}

def check_cooldown(user_id: int, command: str = "guess", cooldown_time: int = None) -> bool:
    """
    Check if user is on cooldown
    Returns: True if on cooldown, False if not
    """
    if cooldown_time is None:
        cooldown_time = COMMAND_COOLDOWNS.get(command, DEFAULT_COOLDOWN)
    
    current_time = time.time()
    
    if user_id not in _user_cooldowns:
        _user_cooldowns[user_id] = {}
    
    if command in _user_cooldowns[user_id]:
        elapsed = current_time - _user_cooldowns[user_id][command]
        if elapsed < cooldown_time:
            return True  # Still on cooldown
    
    # Update cooldown
    _user_cooldowns[user_id][command] = current_time
    return False  # Not on cooldown

def get_remaining_cooldown(user_id: int, command: str = "guess", cooldown_time: int = None) -> int:
    """
    Get remaining cooldown time in seconds
    """
    if cooldown_time is None:
        cooldown_time = COMMAND_COOLDOWNS.get(command, DEFAULT_COOLDOWN)
    
    current_time = time.time()
    
    if user_id in _user_cooldowns and command in _user_cooldowns[user_id]:
        elapsed = current_time - _user_cooldowns[user_id][command]
        if elapsed < cooldown_time:
            return int(cooldown_time - elapsed)
    
    return 0

async def react_to_message(chat_id: int, message_id: int, emoji: str = "✅") -> bool:
    """
    React to a Telegram message with an emoji
    """
    try:
        from shivu import application  # Import here to avoid circular imports
        bot = application.bot
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[emoji]
        )
        return True
    except Exception as e:
        print(f"Failed to react to message: {e}")
        return False
