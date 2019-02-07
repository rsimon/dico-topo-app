import click
import sqlalchemy

from app import create_app

from app.api.placename.facade import PlacenameFacade
from app.models import UserRole, User,  Placename

app = None


def add_default_users(db):
    try:
        UserRole.add_default_roles()
        User.add_default_users()
    except sqlalchemy.exc.IntegrityError as e:
        db.session.rollback()
        print(e)


def make_cli():
    """ Creates a Command Line Interface for everydays tasks

    :return: Click groum
    """
    @click.group()
    @click.option('--config', default="dev")
    def cli(config):
        """ Generates the client"""
        click.echo("Loading the application")
        global app
        app = create_app(config)

    @click.command("db-create")
    def db_create():
        """ Creates a local database
        """
        with app.app_context():
            from app import db
            db.create_all()

            add_default_users(db)

            db.session.commit()
            click.echo("Created the database")

    @click.command("db-recreate")
    def db_recreate():
        """ Recreates a local database. You probably should not use this on
        production.
        """
        with app.app_context():
            from app import db
            db.drop_all()
            db.create_all()

            add_default_users(db)

            db.session.commit()
            click.echo("Dropped then recreated the database")

    @click.command("db-reindex")
    @click.option('--indexes', default="all")
    @click.option('--host', required=True)
    def db_reindex(indexes, host):
        """
        Rebuild the elasticsearch indexes from the current database
        """
        indexes_info = {
            "placenames": {"facade": PlacenameFacade, "model": Placename}
        }

        def reindex_from_info(name, info):

            with app.app_context():
                prefix = "{host}{api_prefix}".format(host=host, api_prefix=app.config["API_URL_PREFIX"])
                print("Reindexing %s... " % name, end="", flush=True)

                index_name = info["facade"].get_index_name()
                app.elasticsearch.indices.delete(index=index_name, ignore=[400, 404])  # remove all records
                for obj in info["model"].query.all():
                    f_obj = info["facade"](prefix, obj)
                    f_obj.reindex("insert", propagate=False)

                print("ok")

        if indexes == "all": # reindex every index configured above
            indexes = ",".join(indexes_info.keys())

        for name in indexes.split(","):
            if name in indexes_info:
                reindex_from_info(name, indexes_info[name])
            else:
                print("Warning: index %s does not exist or is not declared in the cli" % name)

    @click.command("run")
    def run():
        """ Run the application in Debug Mode [Not Recommended on production]
        """
        app.run()

    cli.add_command(db_create)
    cli.add_command(db_recreate)
    cli.add_command(db_reindex)
    cli.add_command(run)

    return cli