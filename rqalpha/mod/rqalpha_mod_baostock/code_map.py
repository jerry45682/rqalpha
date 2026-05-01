def rqalpha_to_baostock(order_book_id):
    code, exchange = order_book_id.split(".")
    if exchange == "XSHG":
        return "sh.{}".format(code)
    if exchange == "XSHE":
        return "sz.{}".format(code)
    raise ValueError("不支持的 RQAlpha 代码: {}".format(order_book_id))


def baostock_to_rqalpha(code):
    exchange, symbol = code.split(".")
    if exchange == "sh":
        return "{}.XSHG".format(symbol)
    if exchange == "sz":
        return "{}.XSHE".format(symbol)
    raise ValueError("不支持的 Baostock 代码: {}".format(code))

