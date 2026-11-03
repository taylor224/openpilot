from collections.abc import Callable

from openpilot.cereal import log

from openpilot.system.ui.widgets.scroller import NavScroller
from openpilot.selfdrive.ui.mici.widgets.button import BigToggle, BigParamControl, BigMultiParamToggle, GreyBigButton
from openpilot.selfdrive.ui.mici.widgets.dialog import BigConfirmationCircleButton
from openpilot.system.ui.lib.application import gui_app
from openpilot.selfdrive.ui.layouts.settings.common import restart_needed_callback, get_bool_safe, param_known
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.mici.layouts.settings.initial_cruise_speed import InitialCruiseSpeedButton

PERSONALITY_TO_INT = log.LongitudinalPersonality.schema.enumerants


class DisableDriverMonitoringConfirmPage(NavScroller):
  def __init__(self, on_confirm: Callable[[], None]):
    super().__init__()

    accept = BigConfirmationCircleButton("disable\ndriver monitoring",
                                         gui_app.texture("icons_mici/setup/driver_monitoring/dm_check.png", 64, 64),
                                         lambda: self.dismiss(on_confirm))

    self._scroller.add_widgets([
      GreyBigButton("disabling\ndriver monitoring", "scroll to continue",
                    gui_app.texture("icons_mici/setup/warning.png", 64, 64)),
      GreyBigButton("", "The cabin camera will stop watching your attention."),
      GreyBigButton("", "ChadolePilot will no longer warn you or force a disengagement when you look away from the road or fall asleep."),
      GreyBigButton("", "Nothing will stop the car from continuing on its own."),
      GreyBigButton("", "You remain fully responsible for watching the road and for the vehicle at all times."),
      accept,
    ])


class TogglesLayoutMici(NavScroller):
  def __init__(self):
    super().__init__()

    self._personality_toggle = BigMultiParamToggle("following distance", "LongitudinalPersonality", ["aggressive", "standard", "relaxed"],
                                                   description="Standard is recommended.\n" +
                                                               "Aggressive follows closer, with firmer gas and braking.\n" +
                                                               "Relaxed leaves more space.\n" +
                                                               "Use the steering wheel distance button on supported cars.")
    self._initial_cruise_speed = InitialCruiseSpeedButton()
    self._initial_cruise_speed.set_visible(lambda: ui_state.CP is not None and ui_state.has_longitudinal_control and not ui_state.CP.pcmCruise)
    is_metric_toggle = BigToggle("use metric units", initial_state=ui_state.params.get_bool("IsMetric"), toggle_callback=self._on_metric_toggle)
    ldw_toggle = BigParamControl("lane departure warnings", "IsLdwEnabled",
                                 description="Warn when you drift across a detected lane line.\n" +
                                             "Only above 31 mph (50 km/h), with no turn signal.")
    always_on_dm_toggle = BigParamControl("always-on driver monitor", "AlwaysOnDM", description="Monitor the driver even when ChadolePilot is not engaged.")
    self._disable_dm_btn = BigToggle("disable driver monitor",
                                     initial_state=get_bool_safe(ui_state.params, "DisableDriverMonitoring"),
                                     toggle_callback=self._on_disable_dm)
    record_front = BigParamControl("record & upload cabin camera", "RecordFront",
                                   description_icon=gui_app.texture("icons_mici/settings/device/cameras.png", 64, 64),
                                   toggle_callback=restart_needed_callback, description="Upload cabin camera data to help improve driver monitoring.")
    record_mic = BigParamControl("record & upload mic audio", "RecordAudio", description_icon=gui_app.texture("icons_mici/microphone.png", 64, 64),
                                 toggle_callback=restart_needed_callback,
                                 description="Record microphone audio while driving.\n" +
                                             "Audio is included in dashcam videos in sunnylink.")
    enable_openpilot = BigParamControl("enable ChadolePilot", "OpenpilotEnabledToggle", toggle_callback=restart_needed_callback,
                                       description="Enable to use ChadolePilot driver assistance.\n" +
                                                   "Disable to use your car's stock driver assistance.")


    self._scroller.add_widgets([
      self._personality_toggle,
      self._initial_cruise_speed,
      is_metric_toggle,
      ldw_toggle,
      always_on_dm_toggle,
      self._disable_dm_btn,
      record_front,
      record_mic,
      enable_openpilot,
    ])

    # Toggle lists
    self._refresh_toggles = (
      ("IsMetric", is_metric_toggle),
      ("IsLdwEnabled", ldw_toggle),
      ("AlwaysOnDM", always_on_dm_toggle),
      ("DisableDriverMonitoring", self._disable_dm_btn),
      ("RecordFront", record_front),
      ("RecordAudio", record_mic),
      ("OpenpilotEnabledToggle", enable_openpilot),
    )

    enable_openpilot.set_enabled(lambda: not ui_state.engaged)
    # unsafe to flip mid-drive; always-on DM has no effect while monitoring is off
    dm_param_known = param_known(ui_state.params, "DisableDriverMonitoring")
    self._disable_dm_btn.set_enabled((lambda: not ui_state.engaged) if dm_param_known else False)
    always_on_dm_toggle.set_enabled(lambda: not get_bool_safe(ui_state.params, "DisableDriverMonitoring"))
    record_front.set_enabled(False if ui_state.params.get_bool("RecordFrontLock") else (lambda: not ui_state.engaged))
    record_mic.set_enabled(lambda: not ui_state.engaged)

    if ui_state.params.get_bool("ShowDebugInfo"):
      gui_app.set_show_touches(True)
      gui_app.set_show_fps(True)

    ui_state.add_engaged_transition_callback(self._update_toggles)

  def _update_state(self):
    super()._update_state()

    if ui_state.sm.updated["selfdriveState"]:
      personality = PERSONALITY_TO_INT[ui_state.sm["selfdriveState"].personality]
      if personality != ui_state.personality and ui_state.started:
        self._personality_toggle.set_value(self._personality_toggle._options[personality])
      ui_state.personality = personality

  def show_event(self):
    super().show_event()
    self._update_toggles()

  def _on_metric_toggle(self, state: bool):
    ui_state.params.put_bool("IsMetric", state, block=True)
    self._update_toggles()

  def _update_toggles(self):
    ui_state.update_params()
    self._initial_cruise_speed.refresh()

    if ui_state.CP is not None:
      self._personality_toggle.set_visible(ui_state.has_longitudinal_control)

    # Refresh toggles from params to mirror external changes
    for key, item in self._refresh_toggles:
      item.set_checked(get_bool_safe(ui_state.params, key))

  def _on_disable_dm(self, state: bool):
    if state:
      # Don't show enabled state until confirm
      self._disable_dm_btn.set_checked(False)

      def on_confirm():
        ui_state.params.put_bool("DisableDriverMonitoring", True)
        self._disable_dm_btn.set_checked(True)

      gui_app.push_widget(DisableDriverMonitoringConfirmPage(on_confirm))
    else:
      ui_state.params.put_bool("DisableDriverMonitoring", state)
