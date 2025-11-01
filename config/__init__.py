from .scalping_settings import ScalpingSettings
from .swing_settings import SwingSettings

__all__ = ['ScalpingSettings', 'SwingSettings']

__version__ = '2.0.0'


def get_settings_for_mode(mode: str):
    """Retorna settings apropriados para o modo"""
    if mode == 'scalping':
        return ScalpingSettings
    elif mode == 'swing':
        return SwingSettings
    else:
        raise ValueError(f"Modo desconhecido: {mode}. Use 'scalping' ou 'swing'")