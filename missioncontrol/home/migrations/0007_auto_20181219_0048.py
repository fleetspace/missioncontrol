# Generated by Django 2.1.4 on 2018-12-19 00:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("home", "0006_cachedaccess")]

    operations = [
        migrations.AlterField(
            model_name="groundstation",
            name="elevation",
            field=models.FloatField(help_text="In meters"),
        )
    ]
