import os
import json

class StateManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.state = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                return json.load(f)
        return {}

    def get_last_id(self, platform):
        return self.state.get(platform)

    def update_last_id(self, platform, snap_id):
        self.state[platform] = str(snap_id)
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, 'w') as f:
            json.dump(self.state, f)