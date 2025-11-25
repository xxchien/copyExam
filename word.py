def encode_state(states, adds):
    """
    将学习状态编码为整数

    Args:
        states: 14位二进制字符串，每2位表示一天的学习状态
        adds: 下次学习需要加的天数 (0, 1, 2, 4, 7, 15, 30)

    Returns:
        count: 编码后的整数值
    """
    return (int(states, 2) << 8) + adds


def decode_state(count):
    """
    从编码值解析出学习状态

    Args:
        count: 编码后的整数值

    Returns:
        tuple: (states, adds, details) - 状态字符串、下次学习天数和详细解析结果
    """
    # 确保count是整数类型
    if isinstance(count, str):
        count = int(count)

    adds = count & 0xFF  # 获取低8位
    states_int = count >> 8  # 获取高位的状态值
    states = bin(states_int)[2:].zfill(14)  # 转换为14位二进制字符串

    # 解析每个复习间隔的状态
    intervals = [0, 1, 2, 4, 7, 15, 30]
    details = {}

    for i, interval in enumerate(intervals):
        # 每2位表示一个间隔的状态
        start_index = 12 - i * 2  # 从左边开始，每个间隔占2位
        state_bits = states[start_index:start_index + 2]

        # 高位表示是否学习了，低位表示是否正确
        learned = state_bits[0] == '1'
        correct = state_bits[1] == '1' if learned else None

        details[f"+{interval}"] = {
            "learned": learned,
            "correct": correct,
            "state_bits": state_bits
        }

    return states, adds, details



if __name__ == "__main__":
    # 初始状态
    states = '00000000000010'
    adds = 30

    # 编码
    count = encode_state(states, adds)
    print(f"编码结果: {count}")

    count = '2796062'  # 字符串类型的count
    # 解码
    states_parsed, adds_parsed, details = decode_state(count)
    print(f"解析结果 - States: {states_parsed}, Adds: {adds_parsed}")
    print("\n详细学习状态:")
    for interval, info in details.items():
        learned_status = "学习了" if info["learned"] else "跳过了"
        correct_status = "正确" if info["correct"] else "错误" if info["correct"] is not None else "未学习"
        print(f"  {interval}天: {learned_status}, {correct_status} (状态位: {info['state_bits']})")