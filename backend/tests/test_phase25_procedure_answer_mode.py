from app.services.diagnosis_formatting import build_structured_diagnosis


def test_build_structured_diagnosis_returns_procedure_mode_for_step_queries():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 101,
                "citation_label": "C1",
                "section_reference": "发动机拆下",
                "section_path": "第3章 发动机拆装 > 3.1 发动机拆下",
                "excerpt": "1. 排放机油 拆下发动机左曲轴箱上的放油螺栓，将发动机内部机油全部放出。",
                "expanded_content": (
                    "1. 排放机油，拆下发动机左曲轴箱上的放油螺栓。\n"
                    "2. 排放冷却液，拆下水泵盖上的放水螺栓。\n"
                    "3. 松开发动机安装螺栓，依次取下固定螺栓。"
                ),
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 102,
                "citation_label": "C2",
                "section_reference": "发动机拆下",
                "section_path": "第3章 发动机拆装 > 3.1 发动机拆下",
                "excerpt": "4. 断开相关线束与软管，避免带载拆卸。",
            },
        ],
        symptom_description="拆下发动机操作顺序",
        answer_mode="procedure",
    )

    assert payload.answer_mode == "procedure"
    assert payload.root_causes == []
    assert payload.most_likely_fault == "拆下发动机"
    assert [item.step_no for item in payload.next_steps[:3]] == [1, 2, 3]
    assert [item.title for item in payload.next_steps[:3]] == [
        "排放机油，拆下发动机左曲轴箱上的放油螺栓",
        "排放冷却液，拆下水泵盖上的放水螺栓",
        "松开发动机安装螺栓，依次取下固定螺栓",
    ]
    assert payload.next_steps[0].raw_text == "1. 排放机油，拆下发动机左曲轴箱上的放油螺栓"
    assert payload.evidence_count == 2


def test_build_structured_diagnosis_auto_infers_procedure_mode():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 101,
                "citation_label": "C1",
                "section_reference": "发动机拆下",
                "section_path": "第3章 发动机拆装 > 3.2 拆卸发动机",
                "excerpt": "1. 排放机油。2. 排放冷却液。",
            }
        ],
        symptom_description="拆下发动机步骤",
    )

    assert payload.answer_mode == "procedure"
    assert payload.most_likely_fault == "拆下发动机"


def test_build_structured_diagnosis_ignores_parts_catalog_lines_for_procedure_steps():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 5,
                "citation_label": "C1",
                "section_reference": "3.2 拆卸发动机",
                "section_path": "三、发动机 > 3.2 拆卸发动机",
                "expanded_content": (
                    "1 非标螺栓 M10×1.5×80 （达克罗） 8 14# 套筒 / 65 ± 5 N·m\n"
                    "2 非标螺栓 M10×1.5×112 （达克罗） 1 14# 套筒 / 65 ± 5 N·m\n"
                    "1. 排放机油 拆下发动机左曲轴箱上的放油螺栓，将发动机内部机油全部放出。\n"
                    "拆下车架上的放油螺栓，将车架内部机油全部放出。"
                ),
            }
        ],
        symptom_description="拆卸发动机步骤",
        answer_mode="procedure",
    )

    assert len(payload.next_steps) == 1
    assert payload.next_steps[0].step_no == 1
    assert payload.next_steps[0].title == "排放机油"
    assert payload.next_steps[0].summary == ""
    assert payload.next_steps[0].sections[0].label == "执行要点"
    assert payload.next_steps[0].sections[0].items == [
        "拆下发动机左曲轴箱上的放油螺栓，将发动机内部机油全部放出",
        "拆下车架上的放油螺栓，将车架内部机油全部放出",
    ]
    assert payload.next_steps[0].raw_text == (
        "1. 排放机油 拆下发动机左曲轴箱上的放油螺栓，将发动机内部机油全部放出。 "
        "拆下车架上的放油螺栓，将车架内部机油全部放出"
    )


def test_build_structured_diagnosis_prefers_same_section_evidence_for_procedure_query():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 6,
                "citation_label": "C1",
                "section_reference": "2.2 拆卸起动电机",
                "section_path": "二、起动电机 > 2.2 拆卸起动电机",
                "excerpt": "1. 拆卸涨紧器。",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 7,
                "citation_label": "C2",
                "section_reference": "3.2 拆卸发动机",
                "section_path": "三、发动机 > 3.2 拆卸发动机",
                "excerpt": "2. 排放冷却液 拆下水泵盖上的放水螺栓，让冷却液自动流出。",
            },
        ],
        symptom_description="拆卸发动机步骤",
        answer_mode="procedure",
    )

    assert payload.evidence_items
    assert payload.evidence_items[0].section == "3.2 拆卸发动机"


def test_build_structured_diagnosis_extracts_install_engine_sections():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 11,
                "citation_label": "C1",
                "section_reference": "3.3 安装发动机",
                "section_path": "三、发动机 > 3.3 安装发动机",
                "expanded_content": (
                    "1. 按反向顺序安装 安装顺序与拆卸顺序相反。 所有螺栓安装后，必须使用扭力扳手校验并打紧至规定扭矩。\n"
                    "2. 安装各类放油 / 放水螺栓 安装 左曲轴箱放油螺栓、车架放油螺栓、水泵盖放水螺栓。 拧紧力矩要求： 放油螺栓：25 ± 4 N·m 放水螺栓：12 ± 1.5 N·m\n"
                    "3. 加注机油 从 发动机右曲轴箱盖加油口 加入： 1600 mL 机油（若未更换机油精滤芯） 1700 mL 机油（若已更换机油精滤芯） 机油规格要求： 粘度：SAE 10W-40 或 SAE 10W-50 质量等级：API SM 级或以上\n"
                    "4. 加注冷却液 向 右水箱 加注冷却液，直至加满。 启动发动机运行 8 ~ 10 秒后关机。 再次向 右水箱 补液至满。 向 副水箱 加注冷却液，使液面位于 F 线与 L 线之间。"
                ),
            }
        ],
        symptom_description="安装发动机步骤",
        answer_mode="procedure",
    )

    assert [item.title for item in payload.next_steps[:4]] == [
        "按反向顺序安装",
        "安装各类放油 / 放水螺栓",
        "加注机油",
        "加注冷却液",
    ]
    assert payload.next_steps[0].sections
    assert payload.next_steps[0].sections[0].label == "执行要点"
    assert payload.next_steps[0].sections[0].items == [
        "安装顺序与拆卸顺序相反",
        "所有螺栓安装后，必须使用扭力扳手校验并打紧至规定扭矩",
    ]
    assert payload.next_steps[1].summary == "安装 左曲轴箱放油螺栓、车架放油螺栓、水泵盖放水螺栓"
    assert payload.next_steps[1].sections[0].label == "拧紧力矩要求"
    assert payload.next_steps[1].sections[0].items == [
        "放油螺栓：25 ± 4 N·m",
        "放水螺栓：12 ± 1.5 N·m",
    ]
    assert payload.next_steps[2].sections[0].label == "从 发动机右曲轴箱盖加油口 加入"
    assert payload.next_steps[2].sections[0].items == [
        "1600 mL 机油（若未更换机油精滤芯）",
        "1700 mL 机油（若已更换机油精滤芯）",
    ]
    assert payload.next_steps[2].sections[1].label == "机油规格要求"
    assert payload.next_steps[2].sections[1].items == [
        "粘度：SAE 10W-40 或 SAE 10W-50",
        "质量等级：API SM 级或以上",
    ]
    assert payload.next_steps[3].sections[0].label == "执行要点"


def test_build_structured_diagnosis_keeps_same_section_install_steps_when_first_hit_scores_highest():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 795,
                "citation_label": "C1",
                "section_reference": "3.3 安装发动机",
                "section_path": "三、发动机 > 3.3 安装发动机",
                "expanded_content": "1. 按反向顺序安装\n安装顺序与拆卸顺序相反。 所有螺栓安装后，必须使用扭力扳手校验并打紧至规定扭矩。",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 796,
                "citation_label": "C2",
                "section_reference": "3.3 安装发动机",
                "section_path": "三、发动机 > 3.3 安装发动机",
                "expanded_content": "2. 安装各类放油\n/ 放水螺栓 安装 左曲轴箱放油螺栓、车架放油螺栓、水泵盖放水螺栓。\n拧紧力矩要求：\n- 放油螺栓：25 ± 4 N·m\n- 放水螺栓：12 ± 1.5 N·m",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 797,
                "citation_label": "C3",
                "section_reference": "3.3 安装发动机",
                "section_path": "三、发动机 > 3.3 安装发动机",
                "expanded_content": "3. 加注机油\n从 发动机右曲轴箱盖加油口 加入：\n- 1600 mL 机油（若未更换机油精滤芯）\n- 1700 mL 机油（若已更换机油精滤芯）\n机油规格要求：\n- 粘度：SAE 10W-40 或 SAE 10W-50\n- 质量等级：API SM 级或以上",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 798,
                "citation_label": "C4",
                "section_reference": "3.3 安装发动机",
                "section_path": "三、发动机 > 3.3 安装发动机",
                "expanded_content": "4. 加注冷却液\n向 右水箱 加注冷却液，直至加满。 启动发动机运行 8 ～ 10 秒后关机。 再次向 右水箱 补液至满。 向 副水箱 加注冷却液，使液面位于 F 线与 L 线之间。",
            },
        ],
        symptom_description="如何安装发动机",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [1, 2, 3, 4]
    assert [item.title for item in payload.next_steps] == [
        "按反向顺序安装",
        "安装各类放油 / 放水螺栓",
        "加注机油",
        "加注冷却液",
    ]
    assert payload.next_steps[2].sections[0].label == "从 发动机右曲轴箱盖加油口 加入"
    assert payload.next_steps[2].sections[0].items == [
        "1600 mL 机油（若未更换机油精滤芯）",
        "1700 mL 机油（若已更换机油精滤芯）",
    ]
    assert payload.next_steps[2].sections[1].label == "机油规格要求"
    assert payload.next_steps[2].sections[1].items == [
        "粘度：SAE 10W-40 或 SAE 10W-50",
        "质量等级：API SM 级或以上",
    ]
    assert payload.next_steps[3].sections[0].label == "执行要点"
    assert payload.next_steps[3].sections[0].items == [
        "向 右水箱 加注冷却液，直至加满",
        "启动发动机运行 8 ～ 10 秒后关机",
        "再次向 右水箱 补液至满",
        "向 副水箱 加注冷却液，使液面位于 F 线与 L 线之间",
    ]


def test_build_structured_diagnosis_prefers_dominant_section_and_keeps_draw_out_step():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 1386,
                "citation_label": "C1",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "expanded_content": "1. 松开固定起动电机螺栓，拆卸起动电机。",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 1387,
                "citation_label": "C2",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "expanded_content": "2. 松开箱体所有螺栓： 先松右曲轴箱上的 M6×30 螺栓， 再对角松左曲轴箱上的螺栓。",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 1388,
                "citation_label": "C3",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "expanded_content": "3. 将左曲轴箱体水平放置（合箱面朝上），抽出： 右曲轴箱体 垫片 定位销",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 1389,
                "citation_label": "C4",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "expanded_content": "4. 依次取下以下部件： 换挡轴 拨叉轴 变速鼓 拨叉 传动主轴 传动副轴",
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 1308,
                "citation_label": "C5",
                "section_reference": "4.7 气缸头 拆卸气缸头",
                "section_path": "四、气缸头与气门 > 4.7 气缸头 拆卸气缸头",
                "expanded_content": "2. 按顺序松开以下紧固件： 气缸体上的 M6×30 螺栓 M8×110 螺栓（件号 12 ） M10 盖形螺母（件号 10 ） 注意： 螺母（ 10 ）必须对角均匀拧松 每次仅松开 1/3 圈，待全部松动后再完全取下",
            },
        ],
        symptom_description="如何拆卸传动装置",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [1, 2, 3, 4]
    assert [item.title for item in payload.next_steps] == [
        "松开固定起动电机螺栓，拆卸起动电机",
        "松开箱体所有螺栓： 先松右曲轴箱上的 M6×30 螺栓， 再对角松左曲轴箱上的螺栓",
        "将左曲轴箱体水平放置（合箱面朝上），抽出： 右曲轴箱体 垫片 定位销",
        "依次取下以下部件： 换挡轴 拨叉轴 变速鼓 拨叉 传动主轴 传动副轴",
    ]


def test_build_structured_diagnosis_prefers_clean_chunk_content_over_polluted_expanded_context():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 2101,
                "citation_label": "C1",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "_content": "3. 将左曲轴箱体水平放置（合箱面朝上），抽出：右曲轴箱体 垫片 定位销",
                "expanded_content": (
                    "2. 松开箱体所有螺栓：先松右曲轴箱上的 M6×30 螺栓，再对角松左曲轴箱上的螺栓。\n"
                    "3. 将左曲轴箱体水平放置（合箱面朝上），抽出：右曲轴箱体 垫片 定位销\n"
                    "4. 依次取下以下部件：换挡轴 拨叉轴 变速鼓 拨叉 传动主轴 传动副轴\n"
                    "8.4 检查传动装置"
                ),
            }
        ],
        symptom_description="如何拆卸传动装置",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [3]
    assert payload.next_steps[0].title == "将左曲轴箱体水平放置（合箱面朝上），抽出：右曲轴箱体 垫片 定位销"


def test_build_structured_diagnosis_prefers_section_with_better_step_continuity():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 3001,
                "citation_label": "C1",
                "section_reference": "8.4 检查传动装置",
                "section_path": "八、传动装置 > 8.4 检查传动装置",
                "expanded_content": "2. 检查拨叉磨损情况，并记录齿面接触状态。",
                "rerank_score": 9.8,
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 3002,
                "citation_label": "C2",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "expanded_content": "1. 松开固定起动电机螺栓，拆卸起动电机。",
                "rerank_score": 8.6,
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 3003,
                "citation_label": "C3",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "expanded_content": "2. 松开箱体所有螺栓：先松右曲轴箱上的 M6×30 螺栓，再对角松左曲轴箱上的螺栓。",
                "rerank_score": 8.4,
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 3004,
                "citation_label": "C4",
                "section_reference": "8.3 拆卸传动装置",
                "section_path": "八、传动装置 > 8.3 拆卸传动装置",
                "expanded_content": "3. 将左曲轴箱体水平放置（合箱面朝上），抽出：右曲轴箱体 垫片 定位销。",
                "rerank_score": 8.2,
            },
        ],
        symptom_description="如何拆卸传动装置",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [1, 2, 3]
    assert all("8.3 拆卸传动装置" == item.section for item in payload.evidence_items[:3])


def test_build_structured_diagnosis_trims_opposite_action_heading_tail():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 4001,
                "citation_label": "C1",
                "section_reference": "4.7 气缸头 拆卸气缸头",
                "section_path": "四、气缸头与气门 > 4.7 气缸头 拆卸气缸头",
                "expanded_content": "3. 取下： 气缸头 导向条 缸体缸头垫片 安装气缸头",
            }
        ],
        symptom_description="如何拆卸气缸头",
        answer_mode="procedure",
    )

    assert payload.next_steps[0].title == "取下： 气缸头 导向条 缸体缸头垫片"


def test_build_structured_diagnosis_filters_opposite_action_steps_within_same_section():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 4002,
                "citation_label": "C1",
                "section_reference": "4.7 气缸头 拆卸气缸头",
                "section_path": "四、气缸头与气门 > 4.7 气缸头 拆卸气缸头",
                "expanded_content": (
                    "1. 拆下凸轮轴\n"
                    "2. 按顺序松开以下紧固件\n"
                    "3. 取下：气缸头 导向条 缸体缸头垫片 安装气缸头\n"
                    "4. 安装气缸头，使用定扭扳手分三次对角拧紧。"
                ),
            }
        ],
        symptom_description="如何拆卸气缸头",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [1, 2, 3]
    assert all(not item.title.startswith("安装") for item in payload.next_steps)


def test_build_structured_diagnosis_prefers_local_step_content_for_dense_inspection_chunks():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 5001,
                "citation_label": "C1",
                "section_reference": "8.4 检查传动装置",
                "section_path": "八、传动装置 > 8.4 检查传动装置",
                "step_anchor": "（ 1 ）检查拨叉 检查部位：",
                "_content": "（ 1 ）检查拨叉 检查部位： 拨叉凸轮从动件（标记 1 ） 拨叉卡爪（标记 2 ） 如有弯曲、损坏或裂纹 → 更换拨叉",
                "expanded_content": (
                    "（ 1 ）检查拨叉 检查部位： 拨叉凸轮从动件（标记 1 ） 拨叉卡爪（标记 2 ） 如有弯曲、损坏或裂纹 → 更换拨叉\n"
                    "（ 2 ）检查拨叉轴 将拨叉轴放在平坦表面滚动： 如弯曲 → 更换拨叉轴"
                ),
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 5002,
                "citation_label": "C2",
                "section_reference": "8.4 检查传动装置",
                "section_path": "八、传动装置 > 8.4 检查传动装置",
                "step_anchor": "（ 2 ）检查拨叉轴 将拨叉轴放在平坦表面滚动：",
                "_content": "（ 2 ）检查拨叉轴 将拨叉轴放在平坦表面滚动： 如弯曲 → 更换拨叉轴",
            },
        ],
        symptom_description="如何检查传动装置",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [1, 2]


def test_build_structured_diagnosis_falls_back_to_step_anchor_when_expanded_context_crosses_steps():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 5001,
                "citation_label": "C1",
                "section_reference": "8.4 检查传动装置",
                "section_path": "八、传动装置 > 8.4 检查传动装置",
                "step_anchor": "（ 2 ）检查拨叉轴 将拨叉轴放在平坦表面滚动： 如弯曲 → 更换拨叉轴",
                "expanded_content": (
                    "（ 1 ）检查拨叉 检查部位： 拨叉凸轮从动件（标记 1 ） 拨叉卡爪（标记 2 ） 如有弯曲、损坏或裂纹 → 更换拨叉\n"
                    "- 将拨叉轴放在平坦表面滚动： 如弯曲 → 更换拨叉轴\n"
                    "- 警告：不要尝试将弯曲的拨叉轴校直。\n"
                    "（ 3 ）检查变速鼓 如有磨损或刮痕 → 更换变速鼓"
                ),
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 5002,
                "citation_label": "C2",
                "section_reference": "8.4 检查传动装置",
                "section_path": "八、传动装置 > 8.4 检查传动装置",
                "step_anchor": "（ 4 ）检查传动主轴与传动副轴 齿轮：磨损或齿伤 → 更换有缺陷的齿轮 挡圈、垫圈：弯曲变形、损坏或松弛 → 更换",
                "expanded_content": (
                    "（ 3 ）检查变速鼓 如有磨损或刮痕 → 更换变速鼓\n"
                    "- 齿轮：磨损或齿伤 → 更换有缺陷的齿轮\n"
                    "- 挡圈、垫圈：弯曲变形、损坏或松弛 → 更换\n"
                    "（ 5 ）检查轴承 卡滞或磨损 → 更换缺陷轴承"
                ),
            },
        ],
        symptom_description="如何检查传动装置",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [2, 4]
    assert "更换拨叉轴" in payload.next_steps[0].raw_text
    assert "挡圈、垫圈" in payload.next_steps[1].raw_text


def test_build_structured_diagnosis_keeps_numbered_subitems_under_parenthesized_inspection_step():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 5101,
                "citation_label": "C1",
                "section_reference": "9.3 检查曲轴与平衡轴",
                "section_path": "九、曲轴与平衡轴 > 9.3 检查曲轴与平衡轴",
                "step_anchor": "（ 2 ）检查曲轴与平衡轴",
                "expanded_content": (
                    "- 用手拨动轴承内圈： 若有 卡滞 或 磨损 现象 → 更换有缺陷的轴承。\n"
                    "- 注意： 箱体上的曲轴轴承 不可左右互换； 曲轴轴承与曲轴上的衬套 一一对应。\n\n"
                    "（ 2 ）检查曲轴与平衡轴\n\n"
                    "1. 曲轴轴向跳动： ≤ 0.03mm\n\n"
                    "2. 连杆大头轴向间隙： 0.15-0.35mm ，用塞尺测量\n\n"
                    "3. 曲柄销与轴瓦径向间隙： 0.03-0.056mm"
                ),
            }
        ],
        symptom_description="如何检查曲轴与平衡轴",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [2]
    assert "曲轴轴向跳动" in payload.next_steps[0].raw_text


def test_build_structured_diagnosis_keeps_full_procedural_sequence_beyond_six_steps():
    payload = build_structured_diagnosis(
        diagnosis_report=None,
        advice_card=None,
        retrieval_results=[
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 6101,
                "citation_label": "C1",
                "section_reference": "3.2 拆卸发动机",
                "section_path": "三、发动机 > 3.2 拆卸发动机",
                "expanded_content": (
                    "1. 关闭点火开关并支撑整车。\n"
                    "2. 拆下左右侧护板。\n"
                    "3. 断开蓄电池负极导线。\n"
                    "4. 放净发动机机油。"
                ),
                "rerank_score": 9.8,
            },
            {
                "title": "摩托车发动机维修手册",
                "chunk_id": 6102,
                "citation_label": "C2",
                "section_reference": "3.2 拆卸发动机",
                "section_path": "三、发动机 > 3.2 拆卸发动机",
                "expanded_content": (
                    "5. 拆下排气管固定螺栓。\n"
                    "6. 拆开发动机线束与油管。\n"
                    "7. 松开发动机悬置螺栓。\n"
                    "8. 将发动机总成从车架中平稳取出。"
                ),
                "rerank_score": 9.4,
            },
        ],
        symptom_description="拆卸发动机步骤",
        answer_mode="procedure",
    )

    assert [item.step_no for item in payload.next_steps] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert payload.next_steps[-1].title == "将发动机总成从车架中平稳取出"
