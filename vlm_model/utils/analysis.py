# utils/analysis.py

import json
from typing import List, Tuple
import openai
import numpy as np
from vlm_model.config import SYSTEM_INSTRUCTION
from vlm_model.constants.behaviors import PROBLEMATIC_BEHAVIORS
from vlm_model.utils.encoding_image import encode_image
from vlm_model.schemas.feedback import FeedbackSections, FeedbackDetails
from pathlib import Path

# OpenAI 모듈을 client로 정의
client = openai

def load_user_prompt() -> str:
    """
    프롬프트 파일을 로드합니다.
    """
    # 현재 파일의 위치를 기준으로 상대 경로 설정
    current_dir = Path(__file__).parent
    prompt_path = current_dir.parent.parent / 'prompt.txt'  # 실제 프로젝트 구조에 맞게 조정
    
    try:
        with prompt_path.open('r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {prompt_path}")
    except Exception as e:
        raise Exception(f"프롬프트 파일을 로드하는 중 오류 발생: {e}")

def parse_feedback_text(feedback_text: str) -> FeedbackSections:
    """
    feedback_text를 FeedbackSections 형식으로 파싱합니다.
    """
    try:
        feedback_json = json.loads(feedback_text)
        if feedback_json.get("problem") == "none":
            return FeedbackSections(
                gaze_processing=FeedbackDetails(improvement="", recommendations=""),
                facial_expression=FeedbackDetails(improvement="", recommendations=""),
                gestures=FeedbackDetails(improvement="", recommendations=""),
                posture_body=FeedbackDetails(improvement="", recommendations=""),
                movement=FeedbackDetails(improvement="", recommendations="")
            )
        
        # 섹션별로 데이터 추출
        feedback_data = {}
        for section_key, field_name in {
            "gaze_processing": "gaze_processing",
            "facial_expression": "facial_expression",
            "gestures": "gestures",
            "posture_body": "posture_body",
            "movement": "movement"
        }.items():
            section = feedback_json.get(section_key, {})
            improvement = section.get("improvement", "").strip()
            recommendations = section.get("recommendations", "").strip()
            feedback_data[field_name] = FeedbackDetails(
                improvement=improvement,
                recommendations=recommendations
            )
        
        return FeedbackSections(**feedback_data)
    
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 디코딩 오류: {str(e)}")
    except Exception as e:
        raise Exception(f"FeedbackSections 생성 실패: {str(e)}")

def analyze_frames(frames: List[np.ndarray], segment_idx: int, duration: int, segment_length: int, system_instruction: str, frame_interval: int = 3) -> Tuple[List[Tuple[np.ndarray, int, int, str]], List[str]]:
    problematic_frames = []
    feedbacks = []

    num_frames = len(frames)
    time_stamps = [
        segment_idx * segment_length + i * frame_interval
        for i in range(num_frames)
    ]

    # 프롬프트 파일 절대 경로 설정
    user_prompt = load_user_prompt()

    for i, (frame, frame_time_sec) in enumerate(zip(frames, time_stamps)):
        minutes = int(frame_time_sec // 60)
        seconds = int(frame_time_sec % 60)
        timestamp = f"{minutes}m {seconds}s"

        img_type = "image/jpeg"

        # 이미지를 인코딩
        img_b64_str = encode_image(frame)

        if img_b64_str is None:
            continue

        # 사용자 메시지 구성
        user_message = f"{user_prompt}\n\n이미지 데이터: data:{img_type};base64,{img_b64_str}"

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # 올바른 모델 이름으로 수정
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                max_tokens=800,
            )

            # 생성된 텍스트과 문제 행동 추출
            generated_text = response.choices[0].message.content

            # JSON 형식으로 응답을 파싱
            feedback_sections = parse_feedback_text(generated_text)

            # 문제 행동 감지 여부 확인
            problem_detected = any(
                getattr(feedback_sections, field).improvement for field in feedback_sections.__fields__
            )

            # 디버깅을 위해 감지된 문제 행동 출력
            detected_behaviors = [
                field for field in feedback_sections.__fields__ 
                if getattr(feedback_sections, field).improvement
            ]
            print(f"[디버그] 프레임 {i+1} 응답 텍스트: {generated_text}")
            print(f"[디버그] 감지된 문제 행동: {detected_behaviors}")
            print(f"[디버그] PROBLEMATIC_BEHAVIORS 리스트: {PROBLEMATIC_BEHAVIORS}")

            if problem_detected:
                # 프레임과 세그먼트 정보를 저장
                problematic_frames.append((frame, segment_idx + 1, i + 1, timestamp))
                feedbacks.append(generated_text)

        except client.error.OpenAIError as e:
            print(f"프레임 {i+1} 처리 중 OpenAI 오류 발생: {e}")
        except ValueError as ve:
            print(f"프레임 {i+1} 피드백 파싱 중 오류 발생: {ve}")
        except Exception as e:
            print(f"프레임 {i+1} 처리 중 오류 발생: {e}")

    return problematic_frames, feedbacks