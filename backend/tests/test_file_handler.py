from app.utils.file_handler import get_file_size, validate_file_size, validate_file_type


def test_validate_file_type_valid():
    # 只支持 PDF
    assert validate_file_type("document.pdf") is True
    assert validate_file_type("document.PDF") is True


def test_validate_file_type_invalid():
    # 不支持其他格式
    assert validate_file_type("document.docx") is False
    assert validate_file_type("document.pptx") is False
    assert validate_file_type("document.txt") is False
    assert validate_file_type("virus.exe") is False


def test_validate_file_size_valid():
    # 50MB 以内
    assert validate_file_size(1024) is True  # 1KB
    assert validate_file_size(1048576) is True  # 1MB
    assert validate_file_size(52428800) is True  # 50MB


def test_validate_file_size_invalid():
    # 超过 50MB
    assert validate_file_size(52428801) is False  # 50MB + 1
    assert validate_file_size(104857600) is False  # 100MB


def test_validate_file_size_zero():
    # 0 字节（实际实现不检查 0，只检查上限）
    assert validate_file_size(0) is True


def test_get_file_size():
    # 测试函数存在
    assert callable(get_file_size)
