from seoci.pipeline.quality import check_article


def test_heading_structure_is_not_numeric_claim():
    def numeric(body):
        return [f for f in check_article(body, {}, [], [], "guide")["findings"] if f["finding"] == "Unsupported numeric claim"]
    assert not numeric("# Guide\n\n## Step 1: Prepare\n\n## 2. Check")
    assert numeric("# Guide\n\n## Step 1: Improve yields by 80%")
    assert numeric("# Guide\n\n## Step 80% improvement")
