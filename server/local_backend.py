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
import shutil
import git
from urllib.parse import urlparse
import stat

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
LOCAL_REPOS_DIR = os.path.join(LOCAL_STORAGE_DIR, "repositories")
LOCAL_DB_FILE = os.path.join(LOCAL_STORAGE_DIR, "builds.json")

# 디렉토리 생성
os.makedirs(LOCAL_BUILDS_DIR, exist_ok=True)
os.makedirs(LOCAL_REPOS_DIR, exist_ok=True)

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

class GitRepoRequest(BaseModel):
    repo_url: str
    repo_id: str

class CommitAnalysisRequest(BaseModel):
    repo_id: str
    commit_sha: str
    branch_name: str = ""

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

# GitHub API 프록시 엔드포인트
@app.get("/api/github/{path:path}")
async def github_proxy(path: str):
    """GitHub API 프록시 (CORS 해결)"""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.github.com/{path}")
            return JSONResponse(
                content=response.json(),
                headers={"Access-Control-Allow-Origin": "*"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def force_remove_readonly(func, path, exc):
    """읽기 전용 파일 강제 삭제"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

@app.post("/analyze_github_repo")
async def analyze_github_repo(request: GitRepoRequest):
    """GitHub 레포지터리 클론 및 분석"""
    try:
        # 영구 저장 디렉토리 설정
        repo_name = request.repo_id.replace('/', '_')
        repo_dir = os.path.join(LOCAL_REPOS_DIR, repo_name)
        
        # 이미 존재하면 강제 삭제 후 재클론
        if os.path.exists(repo_dir):
            try:
                shutil.rmtree(repo_dir, onerror=force_remove_readonly)
            except Exception as e:
                print(f"기존 폴더 삭제 실패: {e}")
        
        # Git 클론
        try:
            print(f"📥 클론 중: {request.repo_url} -> {repo_dir}")
            git.Repo.clone_from(request.repo_url, repo_dir)
            print(f"✅ 클론 완료: {repo_dir}")
        except Exception as e:
            return {"error": f"레포지터리 클론 실패: {str(e)}"}
        
        # 프로젝트 분석
        return analyze_project_directory(repo_dir)
            
    except Exception as e:
        return {"error": f"분석 실패: {str(e)}"}

@app.post("/analyze_commit_changes")
async def analyze_commit_changes(request: CommitAnalysisRequest):
    """커밋 변경사항 분석"""
    try:
        # 레포지터리 디렉토리 경로
        repo_name = request.repo_id.replace('/', '_')
        repo_dir = os.path.join(LOCAL_REPOS_DIR, repo_name)
        
        if not os.path.exists(repo_dir):
            return {"error": "레포지터리를 찾을 수 없습니다. 먼저 레포지터리를 분석해주세요."}
        
        # Git 레포지터리 객체 생성
        repo = git.Repo(repo_dir)
        
        # 커밋 객체 가져오기
        try:
            commit = repo.commit(request.commit_sha)
        except Exception as e:
            return {"error": f"커밋을 찾을 수 없습니다: {str(e)}"}
        
        # 커밋의 변경사항 분석
        files_data = []
        total_additions = 0
        total_deletions = 0
        difficulty_scores = []
        
        # 부모 커밋과 비교하여 변경사항 추출
        if commit.parents:
            parent_commit = commit.parents[0]
            diff = parent_commit.diff(commit, create_patch=True)
            
            for diff_item in diff:
                file_path = diff_item.a_path or diff_item.b_path
                if not file_path:
                    continue
                    
                file_ext = os.path.splitext(file_path)[1].lower()
                supported_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go'}
                if file_ext not in supported_extensions:
                    continue
                
                try:
                    # Git stats를 사용하여 정확한 변경사항 통계 가져오기
                    stats = commit.stats.files.get(file_path, {'insertions': 0, 'deletions': 0})
                    added_lines = stats.get('insertions', 0)
                    deleted_lines = stats.get('deletions', 0)
                    
                    # diff가 없으면 patch에서 직접 계산
                    if added_lines == 0 and deleted_lines == 0 and diff_item.diff:
                        try:
                            diff_text = diff_item.diff.decode('utf-8', errors='ignore')
                            for line in diff_text.split('\n'):
                                if line.startswith('+') and not line.startswith('+++'):
                                    added_lines += 1
                                elif line.startswith('-') and not line.startswith('---'):
                                    deleted_lines += 1
                        except:
                            pass
                    
                    # 현재 파일 내용 분석
                    current_content = ""
                    current_file_path = os.path.join(repo_dir, file_path)
                    if os.path.exists(current_file_path):
                        with open(current_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            current_content = f.read()
                    elif diff_item.b_blob:  # 새 파일인 경우
                        current_content = diff_item.b_blob.data_stream.read().decode('utf-8', errors='ignore')
                    
                    if current_content or added_lines > 0:
                        file_analysis = analyze_commit_file_changes(
                            file_path, current_content, added_lines, deleted_lines
                        )
                        
                        if file_analysis:
                            files_data.append(file_analysis)
                            total_additions += added_lines
                            total_deletions += deleted_lines
                            difficulty_scores.append(file_analysis['difficulty_score'])
                
                except Exception as e:
                    print(f"파일 분석 오류 {file_path}: {e}")
                    continue
        
        # 요약 정보 계산
        summary = {
            'total_files': len(files_data),
            'total_additions': total_additions,
            'total_deletions': total_deletions,
            'avg_difficulty': round(sum(difficulty_scores) / len(difficulty_scores), 2) if difficulty_scores else 0
        }
        
        return {
            'summary': summary,
            'files': files_data,
            'commit_info': {
                'sha': request.commit_sha,
                'message': commit.message,
                'author': commit.author.name,
                'date': commit.committed_datetime.isoformat(),
                'branch': request.branch_name
            }
        }
        
    except Exception as e:
        return {"error": f"커밋 분석 실패: {str(e)}"}

def analyze_commit_file_changes(file_path, content, added_lines, deleted_lines):
    """커밋에서 변경된 파일 분석"""
    try:
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 코드 라인과 주석 라인 구분
        code_lines = 0
        comment_lines = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            elif stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                comment_lines += 1
            else:
                code_lines += 1
        
        # 추가/삭제된 라인에서 코드와 주석 구분 (간단한 추정)
        code_lines_added = max(0, int(added_lines * 0.8))  # 80%가 코드라고 가정
        comment_lines_added = added_lines - code_lines_added
        code_lines_deleted = max(0, int(deleted_lines * 0.8))
        comment_lines_deleted = deleted_lines - code_lines_deleted
        
        # 변경사항 기반 난이도 계산
        change_complexity = added_lines + deleted_lines
        file_complexity = calculate_complexity(content)
        
        # 난이도 점수 (1-10)
        difficulty = min(10, max(1, 
            (change_complexity // 10) +  # 변경량 기반
            (file_complexity // 20) +    # 파일 복잡도 기반
            (1 if added_lines > deleted_lines else 0)  # 추가가 더 많으면 +1
        ))
        
        # 개발자 수준 추정
        dev_level = get_developer_level(difficulty)
        
        return {
            'file_path': file_path,
            'code_lines': code_lines,
            'code_lines_added': code_lines_added,
            'code_lines_deleted': code_lines_deleted,
            'comment_lines': comment_lines,
            'comment_lines_added': comment_lines_added,
            'comment_lines_deleted': comment_lines_deleted,
            'difficulty_score': difficulty,
            'developer_level': dev_level,
            'total_additions': added_lines,
            'total_deletions': deleted_lines
        }
        
    except Exception as e:
        print(f"커밋 파일 분석 오류: {e}")
        return None

@app.post("/analyze_project")
async def analyze_project(files: List[UploadFile] = File(...)):
    """업로드된 파일들 분석"""
    try:
        # 임시 디렉토리에 파일들 저장
        with tempfile.TemporaryDirectory() as temp_dir:
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                content = await file.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
            
            # 프로젝트 분석
            return analyze_project_directory(temp_dir)
            
    except Exception as e:
        return {"error": f"분석 실패: {str(e)}"}

def analyze_project_directory(project_dir):
    """프로젝트 디렉토리 분석"""
    extractor = FunctionExtractor()
    files_data = []
    total_lines = 0
    total_files = 0
    complexity_scores = []
    difficulty_scores = []
    
    # 지원하는 파일 확장자
    supported_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go'}
    
    for root, dirs, files in os.walk(project_dir):
        # 불필요한 디렉토리 제외
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'build', 'dist']]
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in supported_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # 파일 분석
                    file_analysis = analyze_file(file_path, content, extractor)
                    if file_analysis:
                        files_data.append(file_analysis)
                        total_lines += file_analysis['total_lines']
                        total_files += 1
                        complexity_scores.append(file_analysis['cyclomatic_complexity'])
                        difficulty_scores.append(file_analysis['difficulty_score'])
                        
                except Exception as e:
                    print(f"파일 분석 오류 {file_path}: {e}")
                    continue
    
    # 요약 정보 계산
    summary = {
        'total_files': total_files,
        'total_lines': total_lines,
        'avg_complexity': round(sum(complexity_scores) / len(complexity_scores), 2) if complexity_scores else 0,
        'max_difficulty': max(difficulty_scores) if difficulty_scores else 0,
        'total_estimated_hours': sum(f['estimated_dev_hours'] for f in files_data)
    }
    
    return {
        'summary': summary,
        'files': files_data
    }

def analyze_file(file_path, content, extractor):
    """개별 파일 분석"""
    try:
        lines = content.split('\n')
        total_lines = len(lines)
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('//')])
        comment_lines = total_lines - code_lines
        comment_ratio = f"{round((comment_lines / total_lines) * 100, 1)}%" if total_lines > 0 else "0%"
        
        # 복잡도 계산 (간단한 휴리스틱)
        complexity = calculate_complexity(content)
        
        # 기술 스택 감지
        tech_stack = detect_tech_stack(file_path, content)
        
        # 난이도 점수 (1-10)
        difficulty = min(10, max(1, complexity // 5 + len(tech_stack)))
        
        # 개발자 수준 추정
        dev_level = get_developer_level(difficulty)
        
        # 예상 개발 시간 (시간)
        estimated_hours = max(1, (code_lines // 50) + (complexity // 10))
        
        return {
            'file_path': os.path.relpath(file_path),
            'total_lines': total_lines,
            'code_lines': code_lines,
            'code_comment_ratio': comment_ratio,
            'cyclomatic_complexity': complexity,
            'maintainability_index': max(0, min(100, 100 - complexity)),
            'estimated_dev_hours': estimated_hours,
            'difficulty_score': difficulty,
            'developer_level': dev_level,
            'pattern_score': min(10, max(1, 8 - (complexity // 10))),
            'optimization_score': min(10, max(1, 7 + (comment_lines // 10))),
            'best_practices_score': min(10, max(1, 6 + len(tech_stack))),
            'tech_stack': tech_stack
        }
    except Exception as e:
        print(f"파일 분석 오류: {e}")
        return None

def calculate_complexity(content):
    """코드 복잡도 계산"""
    complexity = 1  # 기본 복잡도
    
    # 제어 구조 카운트
    control_keywords = ['if', 'else', 'elif', 'for', 'while', 'switch', 'case', 'try', 'catch', 'except']
    for keyword in control_keywords:
        complexity += content.lower().count(keyword)
    
    # 함수/메서드 카운트
    complexity += content.count('def ') + content.count('function ') + content.count('public ') + content.count('private ')
    
    return min(100, complexity)

def detect_tech_stack(file_path, content):
    """기술 스택 감지"""
    tech_stack = []
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # 파일 확장자 기반
    ext_mapping = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.cs': 'C#',
        '.php': 'PHP',
        '.rb': 'Ruby',
        '.go': 'Go'
    }
    
    if file_ext in ext_mapping:
        tech_stack.append(ext_mapping[file_ext])
    
    # 프레임워크/라이브러리 감지
    frameworks = {
        'react': 'React',
        'vue': 'Vue.js',
        'angular': 'Angular',
        'django': 'Django',
        'flask': 'Flask',
        'spring': 'Spring',
        'express': 'Express.js',
        'jquery': 'jQuery'
    }
    
    content_lower = content.lower()
    for keyword, framework in frameworks.items():
        if keyword in content_lower:
            tech_stack.append(framework)
    
    return list(set(tech_stack))  # 중복 제거

def get_developer_level(difficulty):
    """난이도 기반 개발자 수준 추정"""
    if difficulty <= 3:
        return "초급"
    elif difficulty <= 6:
        return "중급"
    elif difficulty <= 8:
        return "고급"
    else:
        return "전문가"

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