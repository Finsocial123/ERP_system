from app.core.database import Base, engine
from app.core.migrations import run_startup_migrations


def main() -> None:
    Base.metadata.create_all(bind=engine)
    run_startup_migrations(engine)
    print("Startup migrations completed.")


if __name__ == "__main__":
    main()


