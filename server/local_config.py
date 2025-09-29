# 로컬 환경 설정
import os
import json
from typing import Dict, List

# 로컬 저장소 경로
LOCAL_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "local_storage")
LOCAL_BUILDS_DIR = os.path.join(LOCAL_STORAGE_DIR, "builds")
LOCAL_DB_FILE = os.path.join(LOCAL_STORAGE_DIR, "builds.json")

# 디렉토리 생성
os.makedirs(LOCAL_BUILDS_DIR, exist_ok=True)

class LocalStorage:
    def __init__(self):
        self.db_file = LOCAL_DB_FILE
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        if not os.path.exists(self.db_file):
            with open(self.db_file, 'w') as f:
                json.dump([], f)
    
    def save_build(self, build_data: Dict):
        builds = self.get_all_builds()
        builds.append(build_data)
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(builds, f, ensure_ascii=False, indent=2)
    
    def get_all_builds(self) -> List[Dict]:
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def get_build(self, build_id: str) -> Dict:
        builds = self.get_all_builds()
        for build in builds:
            if build.get('build_id') == build_id:
                return build
        return {}

# 로컬 스토리지 인스턴스
local_storage = LocalStorage()