import funktools


@funktools.CLI(__name__)
def entrypoint() -> None:
    print('haha')


if __name__ == '__main__':
    funktools.CLI(__name__).run()
