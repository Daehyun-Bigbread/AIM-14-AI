# utils/encoding_iamge.py

import cv2
import base64
import numpy as np
from typing import Optional

def encode_image(image: np.ndarray, max_size: tuple = (256, 256), quality: int = 70) -> Optional[str]:
    """
    이미지를 리사이즈하고 JPEG 형식으로 인코딩한 후 Base64 문자열로 반환합니다.
    """
    try:
        # 현재 이미지의 크기 가져오기
        height, width = image.shape[:2]
        max_width, max_height = max_size

        # 비율 유지하며 크기 조정
        scaling_factor = min(max_width / width, max_height / height, 1)  # 원본보다 작게만 조정
        new_width = int(width * scaling_factor)
        new_height = int(height * scaling_factor)
        resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

        # JPEG로 인코딩
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        result, encimg = cv2.imencode('.jpg', resized_image, encode_param)
        if not result:
            print("이미지 인코딩에 실패했습니다.")
            return None

        # Base64 인코딩
        img_b64_str = base64.b64encode(encimg.tobytes()).decode('utf-8')
        return img_b64_str
    except Exception as e:
        print(f"이미지 인코딩 중 오류 발생: {e}")
        return None