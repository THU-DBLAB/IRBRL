def tos_base(tos):
    """
    我們定義談到的priority===dscp+ecn
    這裡要設計如何拿到
    """
    dscp=tos>>2
    priority=(2*dscp)+1
    return priority,dscp