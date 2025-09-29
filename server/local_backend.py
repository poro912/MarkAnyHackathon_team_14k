from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import uuid
import os
from datetime import datetime
from typing import List
from pydantic import BaseModel
from function_extractor import FunctionExtractor
import tempfile
import subprocess

# 현재 디렉토리 경로
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=CURRENT_DIR), name="static")

# 로컬 저장소 설정
LOCAL_STORAGE_DIR = os.path.join(CURRENT_DIR, "local_storage")
LOCAL_BUILDS_DIR = os.path.join(LOCAL_STORAGE_DIR, "builds")
LOCAL_DB_FILE = os.path.join(LOCAL_STORAGE_DIR, "builds.json")

# 디렉토리 생성
os.makedirs(LOCAL_BUILDS_DIR, exist_ok=True)

# 로컬 JSON DB 초기화
if not os.path.exists(LOCAL_DB_FILE):
    with open(LOCAL_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

class BuildConfig(BaseModel):
    architecture: str
    runtime: str
    msvc_version: str
    library_type: str
    utilities: List[dict]
    comment: str = ""

def save_to_local_db(build_data):
    """로컬 JSON에 빌드 데이터 저장"""
    try:
        with open(LOCAL_DB_FILE, 'r', encoding='utf-8') as f:
            builds = json.load(f)
    except:
        builds = []
    
    builds.append(build_data)
    
    with open(LOCAL_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(builds, f, ensure_ascii=False, indent=2)

def get_from_local_db():
    """로컬 JSON에서 빌드 데이터 조회"""
    try:
        with open(LOCAL_DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

@app.get("/")
async def read_root():
    return FileResponse(os.path.join(CURRENT_DIR, "index.html"))

@app.get("/{filename}")
async def serve_html(filename: str):
    if filename.endswith('.html'):
        file_path = os.path.join(CURRENT_DIR, filename)
        if os.path.exists(file_path):
            return FileResponse(file_path)
    raise HTTPException(status_code=404)

@app.post("/analyze")
async def analyze_code(files: List[UploadFile] = File(...)):
    extractor = FunctionExtractor()
    utilities = []
    
    for file in files:
        try:
            content = await file.read()
            try:
                text = content.decode('utf-8')
            except:
                text = content.decode('cp949', errors='ignore')
            
            functions = extractor.extract_functions(text)
            for func in functions:
                func['source_file'] = file.filename
            utilities.extend(functions)
            
        except Exception as e:
            print(f"파일 처리 오류: {e}")
            continue
    
    return {"utilities": utilities}

@app.post("/build")
async def build_dll(config: BuildConfig):
    build_id = str(uuid.uuid4())
    file_extension = "dll" if config.library_type == "dll" else "lib"
    
    # 헤더 파일 생성
    header_content = generate_header_file(config.utilities, config.library_type)
    
    # C++ 소스 파일 생성
    cpp_content = "#include <iostream>\n"
    if config.library_type == "dll":
        cpp_content += '#define LIBRARY_API __declspec(dllexport)\n'
    else:
        cpp_content += '#define LIBRARY_API\n'
    
    for utility in config.utilities:
        cpp_content += f"\n{utility.get('code', '// 코드 없음')}\n"
    
    # 임시 파일로 컴파일
    with tempfile.TemporaryDirectory() as temp_dir:
        cpp_file = os.path.join(temp_dir, f"{build_id}.cpp")
        dll_file = os.path.join(temp_dir, f"{build_id}.{file_extension}")
        
        with open(cpp_file, 'w', encoding='utf-8') as f:
            f.write(cpp_content)
        
        try:
            # g++ 컴파일
            if config.library_type == "dll":
                compile_cmd = ["g++", "-shared", "-fPIC", "-std=c++17", "-o", dll_file, cpp_file]
            else:
                obj_file = cpp_file.replace('.cpp', '.o')
                subprocess.run(["g++", "-c", "-std=c++17", "-o", obj_file, cpp_file], check=True)
                compile_cmd = ["ar", "rcs", dll_file.replace('.lib', '.a'), obj_file]
            
            result = subprocess.run(compile_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 로컬에 저장
                local_dll_path = os.path.join(LOCAL_BUILDS_DIR, f"{build_id}.{file_extension}")
                local_header_path = os.path.join(LOCAL_BUILDS_DIR, f"{build_id}.h")
                
                with open(dll_file, 'rb') as src, open(local_dll_path, 'wb') as dst:
                    dst.write(src.read())
                
                with open(local_header_path, 'w', encoding='utf-8') as f:
                    f.write(header_content)
                
                # 빌드 정보 저장
                build_data = {
                    'build_id': build_id,
                    'filename': f"{build_id}.{file_extension}",
                    'header_filename': f"{build_id}.h",
                    'comment': config.comment,
                    'status': 'completed',
                    'local_dll_path': local_dll_path,
                    'local_header_path': local_header_path,
                    'utilities': config.utilities,
                    'timestamp': datetime.now().isoformat()
                }
                
                save_to_local_db(build_data)
                
                return {
                    "build_id": build_id,
                    "status": "completed",
                    "message": "빌드 완료",
                    "file_extension": file_extension
                }
            else:
                raise Exception(f"컴파일 실패: {result.stderr}")
                
        except Exception as e:
            return {"error": f"빌드 실패: {str(e)}"}

@app.get("/builds")
async def get_builds():
    builds = get_from_local_db()
    for build in builds:
        build_id = build.get('build_id')
        if build_id:
            build['dll_download_url'] = f"/download/{build_id}"
            build['header_download_url'] = f"/download/{build_id}/header"
    return {"builds": builds}

@app.get("/download/{build_id}")
async def download_library(build_id: str):
    builds = get_from_local_db()
    build = next((b for b in builds if b.get('build_id') == build_id), None)
    
    if not build:
        raise HTTPException(status_code=404, detail="빌드를 찾을 수 없습니다")
    
    dll_path = build.get('local_dll_path')
    if not dll_path or not os.path.exists(dll_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    
    return FileResponse(dll_path, filename=build.get('filename'))

@app.get("/download/{build_id}/header")
async def download_header(build_id: str):
    builds = get_from_local_db()
    build = next((b for b in builds if b.get('build_id') == build_id), None)
    
    if not build:
        raise HTTPException(status_code=404, detail="빌드를 찾을 수 없습니다")
    
    header_path = build.get('local_header_path')
    if not header_path or not os.path.exists(header_path):
        raise HTTPException(status_code=404, detail="헤더 파일을 찾을 수 없습니다")
    
    return FileResponse(header_path, filename=build.get('header_filename'))

def generate_header_file(utilities, library_type):
    header = f"""#ifndef UTILITY_LIBRARY_H
#define UTILITY_LIBRARY_H

#ifdef __cplusplus
extern "C" {{
#endif

{"#define LIBRARY_API __declspec(dllexport)" if library_type == "dll" else "#define LIBRARY_API"}

"""
    
    for utility in utilities:
        func_name = utility.get('name', 'Unknown')
        params = utility.get('parameters', 'void')
        return_type = utility.get('return_type', 'void').split(' - ')[0].strip()
        header += f"LIBRARY_API {return_type} {func_name}({params});\n"
    
    header += """
#ifdef __cplusplus
}
#endif

#endif // UTILITY_LIBRARY_H
"""
    return header

if __name__ == "__main__":
    import uvicorn
    import platform
    
    # 환경 감지
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        # 윈도우 환경
        host = "127.0.0.1"
        print("🚀 윈도우 로컬 환경에서 서버 시작")
    else:
        # AWS/Linux 환경
        host = "0.0.0.0"
        print("🚀 AWS/Linux 환경에서 서버 시작")
    
    print("💻 기본 기능 활성화")
    print(f"🌐 브라우저에서 http://localhost 접속하세요")
    uvicorn.run(app, host=host, port=80)