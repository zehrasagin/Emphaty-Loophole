"""Separate observable model output using verified prompt/output boundaries."""


def parse_output(raw, *, reasoning, prompt_opens_think=False, finished=True):
    result = {"raw_output": raw, "reasoning_trace": None, "final_answer": None,
              "trace_available": False, "trace_complete": False, "parse_status": "missing_trace"}
    if not raw.strip():
        result['parse_status'] = 'empty_output'
        return result
    if not reasoning:
        result.update(final_answer=raw if finished else None,
                      parse_status="plain_standard_response" if finished else "incomplete_generation")
        return result

    # The official R1 template may supply <think> in the input, so generated text
    # then starts inside that block. Never add the prefix to the raw output.
    text = raw
    opened = prompt_opens_think
    if text.lstrip().startswith("<think>"):
        # Accept one explicit opener even if the template already supplied one.
        text = text.lstrip()[len("<think>"):]
        opened = True
    if not opened:
        if '<think>' in text or text.count('</think>') > 1:
            result['parse_status'] = 'malformed_trace_tags'
        elif '</think>' in text:
            result['parse_status'] = 'missing_open_tag'
            final = text.split('</think>', 1)[1].strip()
            result['final_answer'] = final if finished and final else None
        else:
            result.update(final_answer=raw if finished else None,
                          parse_status='missing_trace' if finished else 'incomplete_generation')
        return result
    if "<think>" in text or text.count("</think>") > 1:
        result["parse_status"] = "malformed_trace_tags"
        return result
    if "</think>" not in text:
        trace = text.strip()
        result.update(reasoning_trace=trace or None, trace_available=bool(trace),
                      parse_status="missing_close_tag" if finished else "truncated_trace")
        return result

    trace, final = (part.strip() for part in text.split("</think>", 1))
    result.update(reasoning_trace=trace or None, trace_available=bool(trace), trace_complete=True)
    if not finished:
        result["parse_status"] = "truncated_final"
    elif not final:
        result["parse_status"] = "missing_final"
    else:
        result.update(final_answer=final, parse_status="parsed" if trace else "empty_trace")
    return result
