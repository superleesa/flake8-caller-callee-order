def a():
    b()
    c()


def b():
    print("b")


def c():
    c()  # allowed recursion
