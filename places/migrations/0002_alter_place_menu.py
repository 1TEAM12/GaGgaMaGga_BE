# Generated by Django 4.1.3 on 2022-12-18 16:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='place',
            name='menu',
            field=models.TextField(null=True, verbose_name='메뉴'),
        ),
    ]
