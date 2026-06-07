"""
image_preprocessing.py — OpenCV Image Preprocessing untuk Tesseract OCR

Pipeline preprocessing untuk meningkatkan kualitas OCR:
1. Grayscale conversion
2. Noise reduction (bilateral filter)
3. Adaptive binarization
4. Deskew detection & correction
5. Morphological cleaning
6. Border removal
"""

import cv2
import numpy as np
from PIL import Image


def preprocess_image_for_ocr(
    pil_image: Image.Image,
    bilateral_d: int = 9,
    bilateral_sigma_color: int = 75,
    bilateral_sigma_space: int = 75,
    adaptive_block_size: int = 15,
    adaptive_c: int = 8,
    deskew_threshold: float = 0.5,
    border_crop_percent: float = 0.02,
) -> Image.Image:
    """
    Preprocessing lengkap untuk gambar halaman PDF sebelum OCR.
    
    Args:
        pil_image: Input gambar dari PyMuPDF render
        bilateral_d: Diameter bilateral filter
        bilateral_sigma_color: Sigma color untuk bilateral filter
        bilateral_sigma_space: Sigma space untuk bilateral filter
        adaptive_block_size: Block size untuk adaptive threshold (harus ganjil)
        adaptive_c: Konstanta C untuk adaptive threshold
        deskew_threshold: Threshold minimum angle (derajat) untuk koreksi skew
        border_crop_percent: Persentase border yang di-crop (0.02 = 2%)
    
    Returns:
        Gambar hasil preprocessing (PIL Image)
    """
    # Convert PIL → numpy array
    img = np.array(pil_image)

    # 1. Border removal — crop tepi untuk hilangkan artefak scan
    if border_crop_percent > 0:
        img = _crop_border(img, border_crop_percent)

    # 2. Grayscale conversion
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    # 3. Noise reduction — bilateral filter mempertahankan tepi teks
    denoised = cv2.bilateralFilter(
        gray, d=bilateral_d,
        sigmaColor=bilateral_sigma_color,
        sigmaSpace=bilateral_sigma_space
    )

    # 4. Adaptive binarization — lebih baik dari Otsu untuk pencahayaan tidak rata
    if adaptive_block_size % 2 == 0:
        adaptive_block_size += 1  # harus ganjil
    binary = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=adaptive_block_size,
        C=adaptive_c
    )

    # 5. Deskew — koreksi kemiringan hasil scan
    binary = _deskew(binary, deskew_threshold)

    # 6. Morphological cleaning — tutup gap kecil dalam karakter
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Convert back to PIL
    return Image.fromarray(cleaned)


def _crop_border(img: np.ndarray, crop_percent: float) -> np.ndarray:
    """Crop border dari gambar untuk menghilangkan artefak tepi scan."""
    h, w = img.shape[:2]
    crop_h = int(h * crop_percent)
    crop_w = int(w * crop_percent)
    return img[crop_h:h - crop_h, crop_w:w - crop_w]


def _deskew(binary_img: np.ndarray, threshold_deg: float) -> np.ndarray:
    """
    Deteksi dan koreksi kemiringan (skew) pada gambar biner.
    Menggunakan minAreaRect pada kontur teks.
    """
    # Invert untuk mendapatkan teks sebagai foreground (putih)
    inverted = cv2.bitwise_not(binary_img)

    # Cari kontur
    coords = np.column_stack(np.where(inverted > 0))
    if len(coords) < 100:
        return binary_img  # tidak cukup kontur untuk deteksi

    # Hitung angle via minAreaRect
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    # Normalisasi angle
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Hanya koreksi jika skew cukup signifikan
    if abs(angle) < threshold_deg:
        return binary_img

    # Rotasi gambar
    h, w = binary_img.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        binary_img, rotation_matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def detect_page_type(pil_image: Image.Image) -> str:
    """
    Deteksi apakah halaman berisi tabel, teks biasa, atau campuran.
    Berdasarkan deteksi garis horizontal & vertikal.
    
    Returns:
        "table", "text", atau "mixed"
    """
    img = np.array(pil_image)

    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    # Edge detection
    edges = cv2.Canny(gray, 50, 150)

    # Deteksi garis horizontal
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    h_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, h_kernel)

    # Deteksi garis vertikal
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    v_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, v_kernel)

    h_count = cv2.countNonZero(h_lines)
    v_count = cv2.countNonZero(v_lines)
    total_pixels = gray.shape[0] * gray.shape[1]
    line_ratio = (h_count + v_count) / total_pixels

    if line_ratio > 0.005:
        return "table"
    elif line_ratio > 0.002:
        return "mixed"
    else:
        return "text"
