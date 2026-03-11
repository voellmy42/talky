import json
import os
import time

class StatsStore:
    def __init__(self, storage_path="~/.talky_stats.json"):
        self.storage_path = os.path.expanduser(storage_path)
        self.stats = {
            "total_dictations": 0,
            "total_words": 0,
            "total_recording_time_seconds": 0.0,
            "total_time_saved_seconds": 0.0
        }
        self.load()

    def load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    self.stats.update(data)
            except Exception as e:
                print(f"[core_stats] Error loading stats: {e}")

    def save(self):
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            print(f"[core_stats] Error saving stats: {e}")

    def add_dictation(self, duration_seconds: float, words_count: int):
        self.stats["total_dictations"] += 1
        self.stats["total_words"] += words_count
        self.stats["total_recording_time_seconds"] += duration_seconds

        # Assume 40 WPM average typing speed -> 1.5 seconds per word
        typing_time_seconds = words_count * 1.5
        
        # Time saved is the difference between typing time and dictation time.
        # Can be negative if they speak very slowly, but we cap at 0 for UI sanity.
        time_saved = max(0.0, typing_time_seconds - duration_seconds)
        self.stats["total_time_saved_seconds"] += time_saved
        
        self.save()

    def get_formatted_stats(self) -> dict:
        """Returns strings for the UI to display neatly."""
        
        # Format time saved
        ts_secs = int(self.stats["total_time_saved_seconds"])
        if ts_secs < 60:
            time_saved_str = f"{ts_secs}s"
        elif ts_secs < 3600:
            time_saved_str = f"{ts_secs // 60}m {ts_secs % 60}s"
        else:
            time_saved_str = f"{ts_secs // 3600}h {(ts_secs % 3600) // 60}m"
            
        # Format WPM
        rec_time = self.stats["total_recording_time_seconds"]
        tot_words = self.stats["total_words"]
        if rec_time > 0:
            # Words per minute
            speed_wpm = int((tot_words / rec_time) * 60)
        else:
            speed_wpm = 0

        return {
            "dictations": str(self.stats["total_dictations"]),
            "time_saved": time_saved_str,
            "speed_wpm": str(speed_wpm)
        }
