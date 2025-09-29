from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import json
import uuid
import os
from datetime import datetime
from typing import List
from pydantic import BaseModel
from decimal import Decimal
from function_extractor import FunctionExtractor
from agents.agent_wrapper import AgentWrapper
from code_analyzer import CodeAnalyzer

def decimal_default(obj):
    """DynamoDB Decimal 타입을 JSON 직렬화 가능하게 변환"""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError
from aws_config import *
import tempfile

# 현재 디렉토리 경로
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
import os

app = FastAPI()

# 정적 파일 서빙 설정
app.mount("/static", StaticFiles(directory=CURRENT_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 - HTML 파일들을 루트에서 직접 서빙
# app.mount("/static", StaticFiles(directory="."), name="static")

# Agent 래퍼 초기화
try:
    init_aws_resources()
    agent_wrapper = AgentWrapper()
    code_analyzer = CodeAnalyzer()
    print("Agent 래퍼 초기화 완료")
except Exception as e:
    print(f"AWS 초기화 실패 (무시): {e}")
    agent_wrapper = None
    code_analyzer = CodeAnalyzer()

class BuildConfig(BaseModel):
    architecture: str
    runtime: str
    msvc_version: str
    library_type: str
    utilities: List[dict]  # 실제 함수 데이터
    comment: str = ""

@app.get("/test.html")
async def serve_test():
    response = FileResponse("test.html")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

@app.get("/system_info.html")
async def serve_system_info():
    response = FileResponse("system_info.html")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

@app.get("/project_evaluation.html")
async def serve_project_evaluation():
    response = FileResponse("project_evaluation.html")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

@app.get("/advanced_utility_extractor.html")
async def serve_advanced_utility_extractor():
    response = FileResponse("advanced_utility_extractor.html")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

@app.delete("/clear_test_data")
async def clear_test_data():
    """테스트 데이터 삭제"""
    try:
        table = dynamodb.Table(EXTRACTION_HISTORY_TABLE)
        
        # 테스트.cpp 파일의 모든 항목 스캔
        response = table.scan(
            FilterExpression="contains(#file, :test_file)",
            ExpressionAttributeNames={'#file': 'file'},
            ExpressionAttributeValues={':test_file': '테스트.cpp'}
        )
        
        # 각 항목 삭제
        for item in response['Items']:
            table.delete_item(Key={'id': item['id']})
        
        return {"success": True, "deleted_count": len(response['Items'])}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/save_extraction")
async def save_extraction(function_data: dict):
    """추출된 함수를 히스토리에 저장"""
    try:
        # 한국 시간으로 변환
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        current_time = datetime.now(kst)
        
        function_data['timestamp'] = current_time.isoformat()
        function_data['extracted_at'] = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # DynamoDB에 저장
        table = dynamodb.Table(EXTRACTION_HISTORY_TABLE)
        function_data['id'] = str(uuid.uuid4())
        
        table.put_item(Item=function_data)
        
        return {"success": True, "message": "추출 히스토리에 저장되었습니다"}
    except Exception as e:
        print(f"추출 히스토리 저장 오류: {e}")
        return {"success": False, "error": str(e)}

@app.post("/analyze")
async def analyze_code(files: List[UploadFile] = File(...)):
    extractor = FunctionExtractor()
    new_utilities = []
    
    for file in files:
        try:
            print(f"파일 처리 시작: {file.filename}")
            
            # 파일 읽기
            content = await file.read()
            print(f"파일 크기: {len(content)} bytes")
            
            # 텍스트 디코딩
            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text = content.decode('cp949')
                except UnicodeDecodeError:
                    text = content.decode('latin-1')
            
            print(f"디코딩된 텍스트 길이: {len(text)}")
            
            # 파일 확장자 확인
            file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'txt'
            print(f"파일 확장자: .{file_extension}")
            
            # 1단계: 수동 함수 추출 (정확한 시그니처)
            print(f"1단계 - 함수 추출: {file.filename}")
            raw_functions = extractor.extract_functions(text)
            print(f"추출된 원본 함수: {len(raw_functions)}개")
            
            # 2단계: AI 리팩토링 (재사용성 향상)
            if agent_wrapper and raw_functions:
                print(f"2단계 - AI 리팩토링: {file.filename}")
                utilities = await agent_wrapper.refactor_for_reusability(raw_functions, text, file_extension)
                print(f"리팩토링된 함수: {len(utilities)}개")
            else:
                utilities = raw_functions
                print("AI 없이 원본 함수 사용")
            
            # 파일 정보 추가
            for util in utilities:
                util['source_file'] = file.filename
                util['file_extension'] = file_extension
            
            new_utilities.extend(utilities)
            
        except Exception as e:
            print(f"파일 처리 오류 ({file.filename}): {e}")
            continue
    
    # 기존 분석 결과와 합치기
    try:
        # 세션에서 기존 결과 가져오기 (간단한 메모리 저장소 사용)
        if not hasattr(app.state, 'analyzed_utilities'):
            app.state.analyzed_utilities = []
        
        # 중복 제거: 같은 파일의 같은 함수명은 새 것으로 교체
        existing_utilities = app.state.analyzed_utilities.copy()
        
        for new_util in new_utilities:
            # 같은 파일의 같은 함수가 있으면 제거
            existing_utilities = [
                util for util in existing_utilities 
                if not (util.get('source_file') == new_util.get('source_file') and 
                       util.get('name') == new_util.get('name'))
            ]
        
        # 새 함수들 추가
        all_utilities = existing_utilities + new_utilities
        
        # 상태 업데이트
        app.state.analyzed_utilities = all_utilities
        
        # 추출 히스토리에 새로 추출된 함수들 저장
        if new_utilities:
            try:
                dynamodb = get_dynamodb_client()
                table = dynamodb.Table(DYNAMODB_TABLE_NAME)
                
                from datetime import timezone, timedelta
                # 한국 시간대 설정
                kst = timezone(timedelta(hours=9))
                
                # 각 함수를 개별적으로 저장
                for utility in new_utilities:
                    function_id = str(uuid.uuid4())
                    table.put_item(
                        Item={
                            'id': function_id,
                            'type': 'function',  # 함수 타입 구분
                            'name': utility.get('name', 'Unknown'),
                            'description': utility.get('description', ''),
                            'purpose': utility.get('purpose', ''),
                            'parameters': utility.get('parameters', ''),
                            'return_type': utility.get('return_type', ''),
                            'code': utility.get('code', ''),
                            'timestamp': datetime.now(kst).isoformat(),
                            'build_id': 'extracted_only',  # 추출만 된 함수 표시
                            'comment': f"{utility.get('source_file', 'Unknown')}에서 추출됨"
                        }
                    )
                print(f"✅ {len(new_utilities)}개 함수가 추출 히스토리에 저장됨")
            except Exception as e:
                print(f"추출 히스토리 저장 실패: {e}")
        
        print(f"📊 전체 함수: {len(all_utilities)}개 (기존: {len(existing_utilities)}개, 새로 추가: {len(new_utilities)}개)")
        
        return {"utilities": all_utilities}
        
    except Exception as e:
        print(f"결과 합치기 오류: {e}")
        return {"utilities": new_utilities}

@app.get("/agent/stats")
async def get_agent_stats():
    """Agent 통계 정보 조회"""
    if not agent_wrapper:
        return {"error": "Agent가 초기화되지 않았습니다."}
    
    return await agent_wrapper.get_agent_stats()

@app.get("/utilities")
async def get_saved_utilities():
    # DynamoDB에서 저장된 유틸리티 조회
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    try:
        response = table.scan()
        utilities = []
        for item in response['Items']:
            if 'utilities' in item:
                utilities.extend(item['utilities'])
        return {"utilities": utilities}
    except Exception as e:
        return {"utilities": []}

@app.post("/build")
async def build_dll(config: BuildConfig):
    print(f"🏗️ 빌드 요청 받음: {len(config.utilities)}개 함수")
    
    # 받은 데이터 확인
    for i, utility in enumerate(config.utilities):
        print(f"  함수 {i+1}: {utility.get('name', 'Unknown')}")
        print(f"    header_declaration 존재: {'header_declaration' in utility}")
        if 'header_declaration' in utility:
            print(f"    header_declaration: {utility['header_declaration']}")
        else:
            print(f"    사용 가능한 필드들: {list(utility.keys())}")
    
    build_id = str(uuid.uuid4())
    
    # 라이브러리 타입에 따른 파일 확장자 결정
    file_extension = "dll" if config.library_type == "dll" else "lib"
    
    # 헤더 파일 생성
    header_content = generate_header_file(config.utilities, config.library_type)
    
    # 실제 C++ 소스 파일 생성
    # 저장된 분석 결과에서 헤더 정보 가져오기
    all_headers = set()
    
    # 저장된 분석 결과와 매칭하여 required_headers 찾기
    stored_utilities = getattr(app.state, 'analyzed_utilities', [])
    
    for utility in config.utilities:
        func_name = utility.get('name')
        
        # 저장된 분석 결과에서 같은 함수 찾기
        stored_util = None
        for stored in stored_utilities:
            if stored.get('name') == func_name:
                stored_util = stored
                break
        
        if stored_util and 'required_headers' in stored_util:
            required_headers = stored_util.get('required_headers', [])
            all_headers.update(required_headers)
            print(f"📋 {func_name}: AI 제공 헤더 {required_headers}")
        else:
            print(f"⚠️ {func_name}: 저장된 헤더 정보 없음, 코드에서 추출")
            # 백업: 코드에서 헤더 자동 감지
            code = utility.get('code', '')
            if 'std::chrono' in code or 'system_clock' in code or 'time_point' in code:
                all_headers.add('<chrono>')
            if 'std::put_time' in code or 'std::setw' in code or 'std::setfill' in code:
                all_headers.add('<iomanip>')
            if 'std::ostringstream' in code or 'std::stringstream' in code:
                all_headers.add('<sstream>')
            if 'std::pow' in code or 'std::sqrt' in code:
                all_headers.add('<cmath>')
            if 'localtime_s' in code or 'localtime_r' in code:
                all_headers.add('<ctime>')
            if 'std::string' in code:
                all_headers.add('<string>')
            if 'std::optional' in code:
                all_headers.add('<optional>')
            if 'std::filesystem' in code or 'filesystem::path' in code:
                all_headers.add('<filesystem>')
            if 'std::ifstream' in code or 'std::ofstream' in code or 'std::fstream' in code:
                all_headers.add('<fstream>')
            if 'std::runtime_error' in code or 'std::exception' in code:
                all_headers.add('<stdexcept>')
    
    # 기본 헤더들 추가
    default_headers = ['<iostream>']
    all_headers.update(default_headers)
    
    print(f"🔧 최종 포함된 헤더들: {sorted(all_headers)}")
    
    cpp_content = ""
    
    # 헤더 포함
    for header in sorted(all_headers):
        cpp_content += f"#include {header}\n"
    
    cpp_content += f"""
#ifdef _WIN32
#define LIBRARY_API __declspec(dllexport)
#else
#define LIBRARY_API __attribute__((visibility("default")))
#endif

"""
    
    # 각 함수의 코드 추가
    for utility in config.utilities:
        cpp_content += f"""
{utility.get('code', '// 코드 없음')}

"""
    
    # 임시 파일 생성 및 컴파일
    import tempfile
    import subprocess
    import os
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cpp_file = os.path.join(temp_dir, f"{build_id}.cpp")
        dll_file = os.path.join(temp_dir, f"{build_id}.{file_extension}")
        
        # C++ 파일 작성
        with open(cpp_file, 'w', encoding='utf-8') as f:
            f.write(cpp_content)
        
        print(f"🔨 C++ 컴파일 시작: {cpp_file}")
        
        try:
            # g++ 컴파일 (Linux 환경)
            if config.library_type == "dll":
                compile_cmd = [
                    "g++", "-shared", "-fPIC", "-std=c++17",
                    "-o", dll_file, cpp_file
                ]
            else:
                compile_cmd = [
                    "ar", "rcs", dll_file.replace('.lib', '.a'),
                    cpp_file.replace('.cpp', '.o')
                ]
                # 먼저 오브젝트 파일 생성
                obj_cmd = ["g++", "-c", "-std=c++17", "-o", cpp_file.replace('.cpp', '.o'), cpp_file]
                subprocess.run(obj_cmd, check=True, cwd=temp_dir)
            
            result = subprocess.run(compile_cmd, capture_output=True, text=True, cwd=temp_dir)
            
            if result.returncode == 0:
                print(f"✅ 컴파일 성공!")
                
                # 컴파일된 파일 읽기
                with open(dll_file, 'rb') as f:
                    library_content = f.read()
                    
                # 로컬에 임시 저장
                local_dir = "/tmp/builds"
                os.makedirs(local_dir, exist_ok=True)
                
                local_dll_path = os.path.join(local_dir, f"{build_id}.{file_extension}")
                local_header_path = os.path.join(local_dir, f"{build_id}.h")
                
                with open(local_dll_path, 'wb') as f:
                    f.write(library_content)
                    
                with open(local_header_path, 'w', encoding='utf-8') as f:
                    f.write(header_content)
                    
                print(f"📁 로컬 저장 완료: {local_dll_path}")
                
                # S3 업로드
                s3 = get_s3_client()
                
                # DLL 파일 업로드
                s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=f"{build_id}.{file_extension}",
                    Body=library_content,
                    ContentType='application/octet-stream'
                )
                
                # 헤더 파일 업로드
                s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=f"{build_id}.h",
                    Body=header_content.encode('utf-8'),
                    ContentType='text/plain'
                )
                
                print(f"☁️ S3 업로드 완료: {build_id}")
                
            else:
                print(f"❌ 컴파일 실패: {result.stderr}")
                library_content = f"// 컴파일 실패: {result.stderr}".encode()
                local_dll_path = None  # 컴파일 실패 시 None
                local_header_path = None
                
        except Exception as e:
            print(f"❌ 컴파일 오류: {e}")
            library_content = f"// 컴파일 오류: {str(e)}".encode()
            local_dll_path = None  # 컴파일 오류 시 None
            local_header_path = None
    
    # S3 URL 생성
    s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{build_id}.{file_extension}"
    header_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{build_id}.h"
    
    # DynamoDB에 빌드 정보 저장 (업로드 전 상태)
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    table.put_item(
        Item={
            'build_id': build_id,
            'filename': f"{build_id}.{file_extension}",
            'header_filename': f"{build_id}.h",
            'comment': config.comment,
            's3_url': s3_url,
            'header_url': header_url,
            'status': 'completed',  # 업로드 완료
            'local_dll_path': local_dll_path,
            'local_header_path': local_header_path,
            'build_config': config.model_dump(),
            'utilities': config.utilities,
            'timestamp': datetime.now().isoformat()
        }
    )
    
    return {
        "build_id": build_id, 
        "status": "built",
        "message": "빌드 완료. 업로드하려면 /upload 엔드포인트를 사용하세요.",
        "file_extension": file_extension
    }

@app.post("/clear")
async def clear_analysis():
    """분석 결과 초기화"""
    if hasattr(app.state, 'analyzed_utilities'):
        count = len(app.state.analyzed_utilities)
        app.state.analyzed_utilities = []
        print(f"🗑️ 분석 결과 초기화: {count}개 함수 삭제")
        return {"message": f"{count}개 함수가 삭제되었습니다.", "utilities": []}
    else:
        return {"message": "삭제할 분석 결과가 없습니다.", "utilities": []}

@app.get("/analyzed")
async def get_analyzed():
    """현재 분석된 함수 목록 조회"""
    if hasattr(app.state, 'analyzed_utilities'):
        utilities = app.state.analyzed_utilities
        print(f"📋 현재 분석된 함수: {len(utilities)}개")
        return {"utilities": utilities}
    else:
        return {"utilities": []}

@app.post("/upload/{build_id}")
async def upload_build(build_id: str, comment: str = ""):
    """빌드된 파일을 S3에 업로드"""
    print(f"📤 업로드 요청: {build_id}")
    
    # DynamoDB에서 빌드 정보 조회
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    try:
        response = table.get_item(Key={'build_id': build_id})
        if 'Item' not in response:
            return {"error": "빌드 ID를 찾을 수 없습니다."}
        
        build_info = response['Item']
        
        if build_info.get('status') != 'built':
            return {"error": "업로드 가능한 빌드가 아닙니다."}
        
        # 로컬 파일 경로
        local_dll_path = build_info.get('local_dll_path')
        local_header_path = build_info.get('local_header_path')
        
        if not os.path.exists(local_dll_path) or not os.path.exists(local_header_path):
            return {"error": "로컬 빌드 파일을 찾을 수 없습니다."}
        
        # S3 업로드
        s3 = get_s3_client()
        
        # DLL 파일 업로드
        with open(local_dll_path, 'rb') as f:
            library_content = f.read()
            
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"{build_id}.{build_info['filename'].split('.')[-1]}",
            Body=library_content,
            ContentType='application/octet-stream'
        )
        
        # 헤더 파일 업로드
        with open(local_header_path, 'r', encoding='utf-8') as f:
            header_content = f.read()
            
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"{build_id}.h",
            Body=header_content.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # URL 생성
        file_extension = build_info['filename'].split('.')[-1]
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{build_id}.{file_extension}"
        header_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{build_id}.h"
        
        # DynamoDB 업데이트 (업로드 완료 상태)
        table.update_item(
            Key={'build_id': build_id},
            UpdateExpression='SET #status = :status, s3_url = :s3_url, header_url = :header_url, upload_comment = :comment, upload_timestamp = :upload_time',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'uploaded',
                ':s3_url': s3_url,
                ':header_url': header_url,
                ':comment': comment,
                ':upload_time': datetime.now().isoformat()
            }
        )
        
        # 로컬 파일 정리
        try:
            os.remove(local_dll_path)
            os.remove(local_header_path)
            print(f"🗑️ 로컬 파일 정리 완료")
        except:
            pass
        
        print(f"✅ 업로드 완료: {s3_url}")
        
        return {
            "build_id": build_id,
            "s3_url": s3_url,
            "header_url": header_url,
            "status": "uploaded",
            "message": "업로드가 완료되었습니다."
        }
        
    except Exception as e:
        print(f"❌ 업로드 오류: {e}")
        return {"error": f"업로드 중 오류가 발생했습니다: {str(e)}"}

def generate_header_file(utilities, library_type):
    """헤더 파일 생성"""
    print(f"🔧 헤더 생성 시작: {len(utilities)}개 함수")
    
    header_content = f"""#ifndef UTILITY_LIBRARY_H
#define UTILITY_LIBRARY_H

#ifdef __cplusplus
extern "C" {{
#endif

"""
    
    if library_type == "dll":
        header_content += """#ifdef BUILDING_DLL
#define LIBRARY_API __declspec(dllexport)
#else
#define LIBRARY_API __declspec(dllimport)
#endif

"""
    else:
        header_content += """#define LIBRARY_API

"""
    
    # 각 함수의 선언 추가
    for i, utility in enumerate(utilities):
        print(f"\n--- 헤더 생성 함수 {i+1}: {utility.get('name', 'Unknown')} ---")
        
        purpose = utility.get('purpose', '함수')
        
        # AI가 제공한 header_declaration을 우선 사용
        if 'header_declaration' in utility and utility['header_declaration'].strip():
            header_declaration = utility['header_declaration']
            print(f"🔧 AI 제공 헤더 사용: {header_declaration}")
        else:
            # 코드에서 함수 시그니처 추출
            code = utility.get('code', '')
            func_name = utility.get('name', 'Unknown')
            
            # 함수 시그니처 추출 (첫 번째 줄에서)
            lines = code.split('\n')
            signature_line = ""
            for line in lines:
                if func_name + '(' in line and not line.strip().startswith('//'):
                    signature_line = line.strip()
                    break
            
            if signature_line:
                # 시그니처에서 중괄호 제거
                if '{' in signature_line:
                    signature_line = signature_line.split('{')[0].strip()
                
                # LIBRARY_API가 없으면 추가
                if not signature_line.startswith('LIBRARY_API'):
                    header_declaration = f"LIBRARY_API {signature_line};"
                else:
                    header_declaration = f"{signature_line};"
                    
                print(f"🔧 코드에서 추출한 헤더: {header_declaration}")
            else:
                # 백업: 수동으로 생성
                parameters = utility.get('parameters', 'void')
                return_type = utility.get('return_type', 'void').split(' - ')[0].strip()
                header_declaration = f"LIBRARY_API {return_type} {func_name}({parameters});"
                print(f"⚠️ 수동 헤더 생성: {header_declaration}")
        
        header_content += f"""// {purpose}
{header_declaration}

"""
    
    header_content += """#ifdef __cplusplus
}
#endif

#endif // UTILITY_LIBRARY_H
"""
    
    return header_content

@app.get("/builds")
async def get_builds():
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    try:
        response = table.scan()
        builds = response['Items']
        
        # 각 빌드에 다운로드 및 문서 생성 URL 추가
        for build in builds:
            build_id = build.get('build_id')
            if build_id:
                build['dll_download_url'] = f"/download/{build_id}"
                build['header_download_url'] = f"/download/{build_id}/header"
                build['generate_docs_url'] = f"/generate_docs/{build_id}"
        
        return {"builds": builds}
    except Exception as e:
        return {"builds": []}

@app.get("/download/{build_id}")
async def download_library(build_id: str):
    # DynamoDB에서 빌드 정보 조회하여 파일 확장자 확인
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    try:
        response = table.get_item(Key={'build_id': build_id})
        if 'Item' in response:
            filename = response['Item'].get('filename', f"{build_id}.dll")
            file_extension = filename.split('.')[-1]
            
            # 로컬 파일 우선 확인
            local_dll_path = response['Item'].get('local_dll_path')
            if local_dll_path and os.path.exists(local_dll_path):
                print(f"📁 로컬 파일 다운로드: {local_dll_path}")
                return FileResponse(local_dll_path, filename=filename)
        else:
            file_extension = "dll"  # 기본값
            filename = f"{build_id}.{file_extension}"
    except:
        file_extension = "dll"
        filename = f"{build_id}.{file_extension}"
    
    # S3에서 파일 다운로드
    s3 = get_s3_client()
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
            s3.download_file(S3_BUCKET_NAME, filename, tmp_file.name)
            return FileResponse(tmp_file.name, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

@app.get("/download/{build_id}/header")
async def download_header(build_id: str):
    """헤더 파일 다운로드"""
    # S3에서 헤더 파일 다운로드
    s3 = get_s3_client()
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.h') as tmp_file:
            s3.download_file(S3_BUCKET_NAME, f"{build_id}.h", tmp_file.name)
            return FileResponse(tmp_file.name, filename=f"{build_id}.h", media_type='text/plain')
    except Exception as e:
        raise HTTPException(status_code=404, detail="헤더 파일을 찾을 수 없습니다")

@app.get("/generate_docs/{build_id}")
async def generate_docs_from_build(build_id: str):
    """빌드 히스토리에서 문서 생성"""
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    try:
        # DynamoDB에서 빌드 정보 조회
        response = table.get_item(Key={'build_id': build_id})
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="빌드를 찾을 수 없습니다")
        
        build_info = response['Item']
        utilities = build_info.get('utilities', [])
        
        if not utilities:
            raise HTTPException(status_code=400, detail="함수 정보가 없습니다")
        
        # 문서 생성 AI 호출
        if agent_wrapper:
            try:
                documentation = await agent_wrapper.generate_documentation(utilities)
                
                # 문서를 S3에 업로드
                s3 = get_s3_client()
                doc_content = f"""# {build_info.get('comment', '유틸리티 라이브러리')} 문서

{documentation}

---
생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
빌드 ID: {build_id}
"""
                
                s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=f"{build_id}_docs.md",
                    Body=doc_content.encode('utf-8'),
                    ContentType='text/markdown'
                )
                
                doc_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{build_id}_docs.md"
                
                # DynamoDB에 문서 URL 업데이트
                table.update_item(
                    Key={'build_id': build_id},
                    UpdateExpression='SET doc_url = :doc_url',
                    ExpressionAttributeValues={':doc_url': doc_url}
                )
                
                return {
                    "success": True,
                    "doc_url": doc_url,
                    "message": "문서가 생성되었습니다"
                }
                
            except Exception as e:
                print(f"문서 생성 오류: {e}")
                raise HTTPException(status_code=500, detail=f"문서 생성 실패: {str(e)}")
        else:
            raise HTTPException(status_code=503, detail="문서 생성 서비스를 사용할 수 없습니다")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"문서 생성 오류: {e}")
        raise HTTPException(status_code=500, detail="문서 생성 중 오류가 발생했습니다")

@app.get("/extraction_history")
async def get_extraction_history():
    """추출 히스토리 조회"""
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    try:
        response = table.scan()
        builds = response['Items']
        
        # 모든 빌드에서 추출된 함수들 수집
        all_functions = []
        for build in builds:
            utilities = build.get('utilities', [])
            for utility in utilities:
                function_data = {
                    'id': f"{build.get('build_id', '')}_{utility.get('name', '')}",
                    'build_id': build.get('build_id', ''),
                    'name': utility.get('name', ''),
                    'description': utility.get('description', ''),
                    'code': utility.get('code', ''),
                    'parameters': utility.get('parameters', ''),
                    'return_type': utility.get('return_type', ''),
                    'purpose': utility.get('purpose', ''),
                    'header_declaration': utility.get('header_declaration', ''),
                    'required_headers': utility.get('required_headers', []),
                    'timestamp': build.get('timestamp', ''),
                    'comment': build.get('comment', '')
                }
                all_functions.append(function_data)
        
        # 시간순 정렬 (최신순)
        all_functions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {"functions": all_functions}
    except Exception as e:
        print(f"추출 히스토리 조회 오류: {e}")
        return {"functions": []}

@app.post("/search_functions")
async def search_functions(request: dict):
    """함수 검색"""
    search_term = request.get('search_term', '').lower()
    
    # 전체 함수 목록 가져오기
    history_response = await get_extraction_history()
    all_functions = history_response.get('functions', [])
    
    if not search_term:
        return {"functions": all_functions}
    
    # 검색 필터링
    filtered_functions = []
    for func in all_functions:
        if (search_term in func.get('name', '').lower() or
            search_term in func.get('description', '').lower() or
            search_term in func.get('purpose', '').lower() or
            search_term in func.get('code', '').lower()):
            filtered_functions.append(func)
    
    return {"functions": filtered_functions}

@app.post("/add_function_to_extractor")
async def add_function_to_extractor(request: dict):
    """선택된 함수를 유틸리티 추출기에 추가"""
    try:
        function_data = request.get('function_data')
        if not function_data:
            raise HTTPException(status_code=400, detail="함수 데이터가 없습니다")
        
        # 함수 코드를 파일 형태로 변환
        code_content = f"""// {function_data.get('description', '함수')}
{function_data.get('code', '')}
"""
        
        # 임시 파일로 저장하여 분석 가능하게 함
        temp_filename = f"extracted_{function_data.get('name', 'function')}.cpp"
        
        return {
            "success": True,
            "code_content": code_content,
            "function_name": function_data.get('name', ''),
            "filename": temp_filename,
            "message": "함수가 유틸리티 추출기에 추가되었습니다"
        }
        
    except Exception as e:
        print(f"함수 추가 오류: {e}")
        raise HTTPException(status_code=500, detail="함수 추가 중 오류가 발생했습니다")

async def download_docs(build_id: str):
    """문서 파일 다운로드"""
    s3 = get_s3_client()
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.md') as tmp_file:
            s3.download_file(S3_BUCKET_NAME, f"{build_id}_docs.md", tmp_file.name)
            return FileResponse(tmp_file.name, filename=f"{build_id}_docs.md", media_type='text/markdown')
    except Exception as e:
        raise HTTPException(status_code=404, detail="문서 파일을 찾을 수 없습니다")

@app.get("/index.html")
async def serve_index():
    """index.html 직접 서빙"""
    try:
        index_path = os.path.join(CURRENT_DIR, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(content="<h1>index.html을 찾을 수 없습니다</h1>")

@app.get("/new")
async def new_interface():
    """새로운 인터페이스 - 캐시 우회용"""
    try:
        index_path = os.path.join(CURRENT_DIR, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(content="<h1>파일을 찾을 수 없습니다</h1>")

@app.get("/")
async def read_root():
    """메인 페이지 제공"""
    try:
        index_path = os.path.join(CURRENT_DIR, "index.html")
        print(f"🔍 Loading index.html from: {index_path}")
        print(f"🔍 File exists: {os.path.exists(index_path)}")
        
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        print(f"🔍 Content length: {len(content)}")
        print(f"🔍 Title in content: {'AI 개발 도구 플랫폼' in content}")
        
        return HTMLResponse(content=content)
    except Exception as e:
        print(f"❌ Index.html 로드 오류: {e}")
        return HTMLResponse(content="<h1>Index.html을 찾을 수 없습니다</h1>")

@app.get("/advanced_utility_extractor.html")
async def serve_utility_extractor():
    """유틸리티 추출기 페이지 제공"""
    return FileResponse(os.path.join(CURRENT_DIR, "advanced_utility_extractor.html"))

@app.get("/project_evaluation.html")
async def serve_project_evaluation():
    """프로젝트 평가 페이지 제공"""
    return FileResponse(os.path.join(CURRENT_DIR, "project_evaluation.html"))

@app.get("/project_analyzer.html")
async def serve_project_analyzer():
    """프로젝트 분석기 페이지 제공"""
    return FileResponse(os.path.join(CURRENT_DIR, "project_analyzer.html"))

@app.get("/download/{build_id}/docs")
async def download_docs(build_id: str):
    """문서 파일 다운로드"""
    s3 = get_s3_client()
    
    try:
        # S3에서 문서 파일 다운로드
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=f"{build_id}_docs.md")
        content = response['Body'].read()
        
        return Response(
            content=content,
            media_type='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename="{build_id}_docs.md"'
            }
        )
    except Exception as e:
        print(f"문서 다운로드 오류: {e}")
        raise HTTPException(status_code=404, detail="문서 파일을 찾을 수 없습니다")

@app.post("/analyze_project")
async def analyze_project(files: List[UploadFile] = File(...)):
    """프로젝트 코드 분석"""
    try:
        temp_dir = tempfile.mkdtemp()
        
        # 파일들을 임시 디렉토리에 저장
        for file in files:
            # 파일명에서 디렉토리 구조 제거
            safe_filename = os.path.basename(file.filename) if file.filename else "unknown"
            file_path = os.path.join(temp_dir, safe_filename)
            
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        
        # 프로젝트 분석 수행
        analysis_result = code_analyzer.analyze_project(temp_dir)
        
        # 임시 디렉토리 정리
        import shutil
        shutil.rmtree(temp_dir)
        
        return analysis_result
        
    except Exception as e:
        return {"error": str(e)}

@app.post('/upload_to_history')
async def upload_to_history(request: dict):
    """빌드 히스토리에 업로드"""
    try:
        build_id = request.get('build_id')
        comment = request.get('comment', '')
        selected_utilities = request.get('selected_utilities', [])
        
        # DynamoDB 테이블 연결
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # DynamoDB에 히스토리 저장
        history_item = {
            'build_id': build_id,  # Primary key
            'id': build_id,        # Alternative key for compatibility
            'timestamp': datetime.now().isoformat(),
            'comment': comment,
            'utilities': selected_utilities,
            'utility_count': len(selected_utilities)
        }
        
        table.put_item(Item=history_item)
        
        return JSONResponse({
            'success': True,
            'message': '빌드 히스토리에 업로드되었습니다!'
        })
        
    except Exception as e:
        print(f"히스토리 업로드 오류: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

@app.get('/get_history')
async def get_history():
    """빌드 히스토리 조회"""
    try:
        # DynamoDB 테이블 연결
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        response = table.scan()
        items = response.get('Items', [])
        
        # Decimal 타입을 일반 타입으로 변환
        def convert_decimals(obj):
            if isinstance(obj, list):
                return [convert_decimals(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_decimals(value) for key, value in obj.items()}
            elif isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            return obj
        
        items = convert_decimals(items)
        
        # 시간순 정렬 (최신순)
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return JSONResponse({
            'success': True,
            'history': items
        })
        
    except Exception as e:
        print(f"히스토리 조회 오류: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

from agents.doc_generator_agent import DocumentationAgent

# 전역 문서 생성 에이전트
doc_agent = None

@app.on_event("startup")
async def startup_event():
    global doc_agent
    try:
        doc_agent = DocumentationAgent()
        print("✅ 문서 생성 AI 초기화 완료")
    except Exception as e:
        print(f"❌ 문서 생성 AI 초기화 실패: {e}")

@app.get("/docs/{build_id}")
async def download_docs(build_id: str):
    """AI 기반 문서 생성 및 다운로드"""
    try:
        # DynamoDB에서 빌드 정보 조회 (두 가지 키로 시도)
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # 먼저 build_id로 조회
        response = table.get_item(Key={'build_id': build_id})
        
        if 'Item' not in response:
            # build_id로 없으면 id로 조회 (히스토리 데이터)
            response = table.get_item(Key={'id': build_id})
        
        if 'Item' not in response:
            # 둘 다 없으면 기본 문서 생성
            doc_content = f"""# 라이브러리 사용법 문서

빌드 ID: {build_id}
생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 사용 방법

1. 라이브러리 파일을 프로젝트에 포함
2. 필요한 헤더 파일 include
3. 함수 호출

## 주의사항

- 적절한 런타임 라이브러리 링크 필요
- 아키텍처 호환성 확인 필요
- 메모리 관리 주의 (malloc/free, new/delete)
"""
        else:
            build_data = response['Item']
            
            # AI를 사용하여 문서 생성
            if doc_agent:
                print(f"AI로 문서 생성 중... (빌드 ID: {build_id})")
                doc_content = await doc_agent.generate_documentation(build_data)
            else:
                # AI 없으면 기본 문서 생성
                doc_content = doc_agent._generate_fallback_doc(build_data) if doc_agent else "문서 생성 에이전트가 초기화되지 않았습니다."
        
        # 임시 파일로 문서 생성하여 다운로드
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(doc_content)
            tmp_file_path = tmp_file.name
        
        return FileResponse(
            tmp_file_path, 
            filename=f"{build_id}_documentation.md", 
            media_type='text/markdown',
            headers={
                "Content-Disposition": f"attachment; filename=\"{build_id}_documentation.md\"",
                "Content-Type": "text/markdown; charset=utf-8"
            }
        )
        
    except Exception as e:
        print(f"문서 다운로드 오류: {e}")
        # 오류 시에도 기본 문서 제공
        doc_content = f"""# 라이브러리 사용법 문서

빌드 ID: {build_id}

문서 생성 중 오류가 발생했습니다.
기본 사용법을 참고하세요.

## 기본 사용 방법

1. 라이브러리 파일을 프로젝트에 포함
2. 헤더 파일 include
3. 함수 호출
"""
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(doc_content)
            tmp_file_path = tmp_file.name
        
        return FileResponse(
            tmp_file_path, 
            filename=f"{build_id}_documentation.md",
            media_type='text/markdown',
            headers={
                "Content-Disposition": f"attachment; filename=\"{build_id}_documentation.md\"",
                "Content-Type": "text/markdown; charset=utf-8"
            }
        )

if __name__ == "__main__":
    import uvicorn
    import platform
    
    # 환경 감지
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        # 윈도우 환경
        host = "127.0.0.1"
        print("🚀 윈도우 환경에서 서버 시작")
    else:
        # AWS/Linux 환경
        host = "0.0.0.0"
        print("🚀 AWS/Linux 환경에서 서버 시작")
    
    print("☁️ 풀 기능 활성화")
    print(f"🌐 브라우저에서 http://localhost 접속하세요")
    uvicorn.run(app, host=host, port=80)
