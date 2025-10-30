# app/services/advanced_machine_detection.py
"""
Advanced Machine Detection handling for future use
Human vs Machine detection for potential re-implementation
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def handle_amd_result(status: str, data: Dict[str, Any]) -> Optional[list]:
    """
    Process AMD results and return appropriate NCCO

    Args:
        status: 'human', 'machine', or other AMD status
        data: Full event data from Vonage

    Returns:
        NCCO list if AMD requires specific handling, None otherwise
    """
    if status == 'human':
        logger.info("Human detected")
        return None  # Let appointment flow handle this

    elif status == 'machine':
        sub_state = data.get('sub_state')
        logger.info(f'Machine detected with substate: {sub_state}')

        if sub_state == 'beep_start':
            logger.info('Beep detected, playing voicemail message')
            return [
                {
                    'action': 'talk',
                    'text': '<speak>Please call us back to confirm your appointment.</speak>',
                    'language': 'en-US',
                    'style': 2,
                    'premium': True
                }
            ]

    return None