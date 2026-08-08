class MartaHandler(object):
    EVENT_HANDLER_DONE = -1

    # Practically infinite (10 years): keeps the normal "mtime() + timeout"
    # arithmetic working while staying below Queue.get()'s timeout limit.
    TIMEOUT_NEVER = 10 * 365 * 24 * 60 * 60

    def __init__(self, marta):
        self.marta = marta

    def initialize(self):
        pass

    def uninitialize(self):
        pass

    def rfid_tag_event(self, tag):
        return

    def rotation_event(self, x, y):
        return

    def player_stop_event(self):
        return

    def button_event(self, pin, millis):
        return
