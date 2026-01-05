# Powermeter classes
class Powermeter:

    def wait_for_message(self, timeout=5):
        pass

    def get_powermeter_watts(self):
        raise NotImplementedError()

    def close(self):
        """Close any open resources (sessions, connections, etc.)"""
        pass
