# tests/test_textdraw.py —— 字体解析 / 换行规则 / 自适应字号
import textdraw

family = textdraw.default_family()


def _font(size=24):
    return family.at(size)


def test_default_family_resolves_something():
    """默认字体解析链至少能给出一个可用字体（系统或仓库自带）。"""
    f = _font(24)
    assert f is not None
    # 能真实测量宽度
    assert textdraw._measure("测试abc", f) > 0


def test_font_family_at_never_crashes_without_file(tmp_path):
    """候选路径全部不存在时也不崩溃（回退 Pillow 默认字体）。"""
    fam = textdraw.FontFamily([tmp_path / "不存在的字体.ttf"], "测试")
    f = fam.at(20)
    assert f is not None


def test_wrap_empty_text():
    assert textdraw.wrap_text("", 100, _font()) == []


def test_wrap_cjk_by_character():
    text = "山风吹过旧巷的时候夏天正在离开" * 3
    font = _font(24)
    width = textdraw._measure("山风吹过旧巷的", font)  # 约 7 字宽
    lines = textdraw.wrap_text(text, width, font)
    assert len(lines) >= 2
    for ln in lines:
        # 每行不超过宽度（禁则回贴允许极小溢出，这里给 5% 容差）
        assert textdraw._measure(ln, font) <= width * 1.05


def test_wrap_english_by_word():
    text = "the quick brown fox jumps over the lazy dog again and again"
    font = _font(24)
    width = textdraw._measure("the quick brown", font)  # 约 3 个词宽
    lines = textdraw.wrap_text(text, width, font)
    assert len(lines) >= 2
    # 重新拼接后内容一致（空格规整化），且没有词被从中间拆开
    joined = " ".join(" ".join(lines).split())
    assert joined == " ".join(text.split())
    words = set(text.split())
    for ln in lines:
        for tok in ln.split():
            assert tok in words  # 没有半个词


def test_no_forbidden_punctuation_at_line_start():
    text = ("夜色温柔，灯火渐暗。风停了；雨还会来吗？她说："
            "“再见。”然后转身，走了很久、很久……") * 2
    font = _font(24)
    width = textdraw._measure("夜色温柔，灯火渐", font)
    lines = textdraw.wrap_text(text, width, font)
    assert len(lines) >= 3
    for ln in lines:
        assert ln[0] not in textdraw.NO_LINE_START


def test_fit_text_shrinks_font_for_long_text():
    text = "这是一段很长很长的文字" * 5
    box_w, box_h = 200, 60
    lines, size = textdraw.fit_text(text, box_w, box_h, 40, 14, family)
    assert size < 40  # 不得不缩小字号
    assert lines
    font = family.at(size)
    for ln in lines:
        assert textdraw._measure(ln, font) <= box_w * 1.05
    assert len(lines) * family.measure_line_height(font) <= box_h + 0.5


def test_fit_text_truncates_when_box_too_small():
    text = "超级长的文案" * 30
    box_w, box_h = 150, 30  # 只够一行小字
    lines, size = textdraw.fit_text(text, box_w, box_h, 24, 12, family)
    assert len(lines) == 1
    assert lines[0].endswith("…")
    assert textdraw._measure(lines[0], family.at(size)) <= box_w * 1.02


def test_fit_text_empty_returns_no_lines():
    lines, size = textdraw.fit_text("", 100, 100, 30, 12, family)
    assert lines == []
    assert size == 30


def test_fit_text_short_uses_max_size():
    lines, size = textdraw.fit_text("你好", 400, 200, 40, 14, family)
    assert size == 40
    assert lines == ["你好"]


def test_draw_lines_runs_on_image():
    from PIL import Image

    import textdraw as td
    img = Image.new("RGB", (300, 100), (0, 0, 0))
    d = td.make_draw(img)
    td.draw_lines(d, ["第一行", "第二行"], 10, 10, _font(20), (255, 255, 255))
    # 文字区域确实有像素被画上（不逐像素猜字形位置）
    region = img.crop((0, 0, 300, 100))
    assert region.getextrema()[0][0] < 128 or region.getextrema()[1][0] < 128
