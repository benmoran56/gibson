import gibson


if __name__ == "__main__":
    server = gibson.Server("0.0.0.0", 6400)
    server.run()
