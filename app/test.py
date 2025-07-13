class CustomException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


try:
    raise Exception("HAHAHAHA YOU SUCK")
except CustomException as e:
    print("Got this exception", e)
