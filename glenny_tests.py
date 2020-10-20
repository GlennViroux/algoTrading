class First:
    def __init__(self):
        print("first")

class Second:
    def __init__(self):
        print("second")

class Third(First, Second):
    def __init__(self):
        First.__init__(self)
        Second.__init__(self)
        print("third")


t = Third()