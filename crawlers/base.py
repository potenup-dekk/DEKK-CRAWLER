class BaseCrawler:
    platform_name = "BASE"
    
    def fetch_new_snaps(self, last_snap_id):
        raise NotImplementedError
        
    def process_and_upload(self, snap_id, today_str):
        raise NotImplementedError