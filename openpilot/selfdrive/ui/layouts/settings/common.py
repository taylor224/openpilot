from openpilot.common.params import UnknownKeyName
from openpilot.selfdrive.ui.ui_state import ui_state


def restart_needed_callback(_=None):
  ui_state.params.put_bool("OnroadCycleRequested", True)


def get_bool_safe(params, key: str, default: bool = False) -> bool:
  # a param added to params_keys.h is unknown until the native lib is rebuilt;
  # a settings panel must not take the whole UI down over that
  try:
    return params.get_bool(key)
  except UnknownKeyName:
    return default


def param_known(params, key: str) -> bool:
  """False when the native params lib predates this key, so it can't be read or written yet."""
  try:
    params.get_bool(key)
  except UnknownKeyName:
    return False
  return True
