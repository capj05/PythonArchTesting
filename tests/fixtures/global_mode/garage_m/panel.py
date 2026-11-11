class Panel:
    def show(self, text):
        print("[garage] " + text)

    def read(self):
        return input("garage> ").strip()
