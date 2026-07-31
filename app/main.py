from app.application.container import ApplicationContainer


def main() -> None:
    application = ApplicationContainer()
    application.run()


if __name__ == "__main__":
    main()
