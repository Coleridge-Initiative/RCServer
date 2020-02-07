from app import APP, build_links
from collections import namedtuple

if __name__ == "__main__":
    Args = namedtuple("Args", ["corpus", "port", "pre"])
    args = Args("min_kg.jsonld", 5000, True)

    build_links(args)
    APP.run()
    
