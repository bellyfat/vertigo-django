from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify

import phonenumbers
from phonenumber_field.modelfields import PhoneNumberField


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()


# Hack to display user full name in forms select field
def override_user_str(self):
    return "{} {}".format(self.first_name, self.last_name)


User.add_to_class('__str__', override_user_str)
User._meta.__setattr__('ordering', ('first_name', ))


class Profile(models.Model):
    """
        Profil data liked to User model
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    license = models.CharField('licence', unique=True, max_length=12)  # 3401 2017 9039 blank=True
    phone = PhoneNumberField('téléphone', null=True, blank=True)
    # birth_date = models.DateField('date de naissance', null=True, blank=True)
    medical_date = models.DateField('date du certificat', null=True, blank=True)
    medical_file = models.FileField('certificat médical', upload_to='medical_certs/%Y/', null=True, blank=True)
    agreement = models.BooleanField('accord de responsabilité', default=False)
    forbidden = models.BooleanField('interdit d\'emprunt', default=False)

    def formatted_phone(self):
        if self.phone:
            return phonenumbers.format_number(self.phone, phonenumbers.PhoneNumberFormat.NATIONAL)
    formatted_phone.short_description = 'téléphone'


class EquipmentType:
    """
        Simple class to handle Equipment type conjugation and reference
    """
    def __init__(self, singular, plural, gender):
        self.singular = singular
        self.plural = plural
        self.url = slugify(plural)
        self.gender = gender


class Equipment(models.Model):
    """
        Model data for all equipment gear
    """

    # Do not modify after database is initialized, only append to the end
    # TODO: add localization if needed
    ROPE = EquipmentType('corde', 'cordes', 'la')
    RAPPEL = EquipmentType('rappel', 'rappels', 'le')
    QUICKDRAW = EquipmentType('dégaines', 'dégaines', 'les')
    LANYARD = EquipmentType('longe', 'longes', 'la')
    HARNESS = EquipmentType('baudrier', 'baudriers', 'le')
    HELMET = EquipmentType('casque', 'casques', 'le')
    CRASHPAD = EquipmentType('crashpad', 'crashpads', 'le')

    TYPE_LIST = [ROPE, RAPPEL, QUICKDRAW, LANYARD, HARNESS, HELMET, CRASHPAD]  # Must be exact number as above

    # TYPES = {}
    # for item in TYPE_LIST:
    #     TYPES[item.ref] = {'singular': item.singular, 'plural': item.plural}

    TYPE_CHOICE = [(equipment.url, equipment.singular) for equipment in TYPE_LIST]

    YEAR_CHOICE = []
    now = timezone.now().year
    for n in range(now, now - 11, -1):
        YEAR_CHOICE.append((n, n))

    ref = models.IntegerField(
        'numéro', help_text='le numéro donné par l\'association', blank=True, null=True, db_index=True)
    type = models.CharField('type', max_length=20, choices=TYPE_CHOICE, default=ROPE.url)
    status = models.BooleanField('en usage', help_text='décocher si réformé', default=True, db_index=True)

    brand = models.CharField('marque', max_length=50, blank=True)
    model = models.CharField('model', max_length=50, blank=True)

    serial_number = models.CharField('numéro de série', max_length=50, blank=True)
    year_of_manufacture = models.IntegerField('date de fabrication', choices=YEAR_CHOICE, blank=True, null=True)
    date_of_purchase = models.DateField('date d\'achat', blank=True, null=True)
    date_of_first_use = models.DateField('date de première utilisation', blank=True, null=True)
    purchase_store = models.CharField('magasin', max_length=50, blank=True)

    caution = models.CharField(
        'avertissement', help_text='un court text accolé au nom du matériel', max_length=50, blank=True)
    comment = models.TextField('commentaire', max_length=250, blank=True)

    class Meta:
        verbose_name = 'équipement'
        verbose_name_plural = 'équipements'
        ordering = ('-status', 'type', 'ref')

    def __str__(self):
        message = " ({})".format(self.caution) if self.caution else ''
        return '{type} n°{ref}{caution}'.format(type=self.get_type_display(), ref=self.ref, caution=message)

    def clean(self):

        now = timezone.now().date()

        if self.year_of_manufacture:
            if self.year_of_manufacture > now.year:
                raise ValidationError(
                    {'year_of_manufacture': 'la date de fabrication doit être antérieur à la date du jour'})

        if self.date_of_purchase:
            if self.date_of_purchase > now:
                raise ValidationError(
                    {'date_of_purchase': 'la date d\'achat doit être antérieur à la date du jour'})

        if self.date_of_first_use:
            if self.date_of_first_use > now:
                raise ValidationError(
                    {'date_of_first_use': 'la date de premier usage doit être antérieur à la date du jour'})

        if self.date_of_purchase and self.year_of_manufacture:
            if self.date_of_purchase.year < self.year_of_manufacture:
                raise ValidationError(
                    {'date_of_purchase': 'la date d\'achat doit être antérieur à la date de fabrication'})

        if self.date_of_purchase and self.date_of_first_use:
            if self.date_of_purchase > self.date_of_first_use:
                raise ValidationError(
                    {'date_of_first_use': 'la date de premier usage doit être postérieur à la date d\'achat'})

        # Don't allow creating an equipment when existing one with same ref and is in use
        if not self.pk:
            if Equipment.objects.filter(type=self.type, ref=self.ref, status=True).exists():
                raise ValidationError(
                    {'ref': 'un·e {} en cours d\'usage existe déjà avec ce numéro'.format(self.get_type_display())})


class Topo(models.Model):

    TOPO = EquipmentType('topo', 'topos', 'le')
    MAP = EquipmentType('carte', 'cartes', 'la')
    GUIDE = EquipmentType('guide rando', 'guides', 'le')
    DVD = EquipmentType('livre/DVD', 'livres/DVDs', 'le')
    TYPE_LIST = [TOPO, MAP, GUIDE, DVD]

    TYPE_CHOICE = [(topo.url, topo.singular) for topo in TYPE_LIST]

    YEAR_CHOICE = []
    for n in range(timezone.now().year, timezone.now().year - 30, -1):
        YEAR_CHOICE.append((n, n))

    DEPT_CHOICE = (
        ('01', 'Ain'),
        ('02', 'Aisne'),
        ('03', 'Allier'),
        ('04', 'Alpes-de-Haute-Provence'),
        ('05', 'Hautes-Alpes'),
        ('06', 'Alpes-Maritimes'),
        ('07', 'Ardèche'),
        ('08', 'Ardennes'),
        ('09', 'Ariège'),
        ('10', 'Aube'),
        ('11', 'Aude'),
        ('12', 'Aveyron'),
        ('13', 'Bouches-du-Rhône'),
        ('14', 'Calvados'),
        ('15', 'Cantal'),
        ('16', 'Charente'),
        ('17', 'Charente-Maritime'),
        ('18', 'Cher'),
        ('19', 'Corrèze'),
        ('21', 'Côte-d\'Or'),
        ('22', 'Côtes-d\'Armor'),
        ('23', 'Creuse'),
        ('24', 'Dordogne'),
        ('25', 'Doubs'),
        ('26', 'Drôme'),
        ('27', 'Eure'),
        ('28', 'Eure-et-Loir'),
        ('29', 'Finistère'),
        ('2A', 'Corse-du-Sud'),
        ('2B', 'Haute-Corse'),
        ('30', 'Gard'),
        ('31', 'Haute-Garonne'),
        ('32', 'Gers'),
        ('33', 'Gironde'),
        ('34', 'Hérault'),
        ('35', 'Ille-et-Vilaine'),
        ('36', 'Indre'),
        ('37', 'Indre-et-Loire'),
        ('38', 'Isère'),
        ('39', 'Jura'),
        ('40', 'Landes'),
        ('41', 'Loir-et-Cher'),
        ('42', 'Loire'),
        ('43', 'Haute-Loire'),
        ('44', 'Loire-Atlantique'),
        ('45', 'Loiret'),
        ('46', 'Lot'),
        ('47', 'Lot-et-Garonne'),
        ('48', 'Lozère'),
        ('49', 'Maine-et-Loire'),
        ('50', 'Manche'),
        ('51', 'Marne'),
        ('52', 'Haute-Marne'),
        ('53', 'Mayenne'),
        ('54', 'Meurthe-et-Moselle'),
        ('55', 'Meuse'),
        ('56', 'Morbihan'),
        ('57', 'Moselle'),
        ('58', 'Nièvre'),
        ('59', 'Nord'),
        ('60', 'Oise'),
        ('61', 'Orne'),
        ('62', 'Pas-de-Calais'),
        ('63', 'Puy-de-Dôme'),
        ('64', 'Pyrénées-Atlantiques'),
        ('65', 'Hautes-Pyrénées'),
        ('66', 'Pyrénées-Orientales'),
        ('67', 'Bas-Rhin'),
        ('68', 'Haut-Rhin'),
        ('69', 'Rhône'),
        ('70', 'Haute-Saône'),
        ('71', 'Saône-et-Loire'),
        ('72', 'Sarthe'),
        ('73', 'Savoie'),
        ('74', 'Haute-Savoie'),
        ('75', 'Paris'),
        ('76', 'Seine-Maritime'),
        ('77', 'Seine-et-Marne'),
        ('78', 'Yvelines'),
        ('79', 'Deux-Sèvres'),
        ('80', 'Somme'),
        ('81', 'Tarn'),
        ('82', 'Tarn-et-Garonne'),
        ('83', 'Var'),
        ('84', 'Vaucluse'),
        ('85', 'Vendée'),
        ('86', 'Vienne'),
        ('87', 'Haute-Vienne'),
        ('88', 'Vosges'),
        ('89', 'Yonne'),
        ('90', 'Territoire de Belfort'),
        ('91', 'Essonne'),
        ('92', 'Hauts-de-Seine'),
        ('93', 'Seine-Saint-Denis'),
        ('94', 'Val-de-Marne'),
        ('95', 'Val-d\'Oise'),
        ('971', 'Guadeloupe'),
        ('972', 'Martinique'),
        ('973', 'Guyane'),
        ('974', 'La Réunion'),
        ('976', 'Mayotte'),
        ('975', 'Saint-Pierre-et-Miquelon'),
        ('977', 'Saint-Barthélemy'),
        ('978', 'Saint-Martin'),
        ('984', 'Terres australes et antarctiques françaises'),
        ('986', 'Wallis et Futuna'),
        ('987', 'Polynésie française'),
        ('988', 'Nouvelle-Calédonie'),
        ('989', 'Île de Clipperton')
    )

    title = models.CharField('titre', max_length=70, blank=True, null=True)
    ref = models.CharField('référence', max_length=70, blank=True, null=True)
    dept = models.CharField('département', max_length=3, choices=DEPT_CHOICE, blank=True, null=True)
    type = models.CharField('type', max_length=10, choices=TYPE_CHOICE, default='climbing', blank=True, null=True)
    year_of_edition = models.IntegerField('année d\'édition', choices=YEAR_CHOICE, blank=True, null=True)
    date_of_purchase = models.DateField('date d\'achat', blank=True, null=True)
    cover = models.ImageField('couverture', upload_to='topos', blank=True, null=True)
    status = models.BooleanField('disponible', help_text='décocher si perdu ou retiré', default=True, db_index=True)

    def cover_html(self):
        return mark_safe('<img src="/static/media/{}" width="64" />'.format(self.cover))
    cover_html.short_description = 'Couverture'

    def __str__(self):
        return '{type} {title}'.format(type=self.get_type_display(), title=self.title)

    class Meta:
        verbose_name = 'topo'
        verbose_name_plural = 'topos'


class Borrowing(models.Model):
    """Borrowing model linking an Equipment to a User"""

    manager = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='responsable matos', blank=True, null=True)
    date = models.DateField('emprunté le', db_index=True)  # default=timezone.now

    class Meta:
        abstract = True

    @property
    def color(self):
        diff = timezone.now().date() - self.date
        d = int(diff.days)
        color = 'dark'
        if d < 2:
            color = 'success'
        elif d < 7:
            color = 'secondary'
        elif d < 14:
            color = 'warning'
        elif d < 21:
            color = 'danger'
        return color


class EquipmentBorrowing(Borrowing):
    """Borrowing relation between an Equipment and a User"""

    user = models.ForeignKey(User, on_delete=models.PROTECT,
                             related_name='equipment_borrowers', verbose_name='par', blank=True, null=True)
    item = models.ForeignKey(Equipment, on_delete=models.PROTECT, verbose_name='équipement')

    class Meta:
        verbose_name = 'emprunt de matériel'
        verbose_name_plural = 'emprunts de matériel'
        ordering = ('-date', '-id')

    def __str__(self):
        return 'Emprunt {item} par {user}'.format(item=self.item, user=self.user)


class TopoBorrowing(Borrowing):
    """Borrowing model linking a Topo or Map to a User"""

    user = models.ForeignKey(User, on_delete=models.PROTECT,
                             related_name='topo_borrowers', verbose_name='par', blank=True, null=True)
    item = models.ForeignKey(Topo, on_delete=models.PROTECT, verbose_name='topo')

    class Meta:
        verbose_name = 'emprunt de topo'
        verbose_name_plural = 'emprunts de topo'
        ordering = ('-date', '-id')

    def __str__(self):
        return 'Emprunt {item} par {user}'.format(item=self.item, user=self.user)


@receiver(post_save, sender=Equipment)
def create_equipment(sender, instance, created, **kwargs):
    if created:
        EquipmentBorrowing.objects.create(item=instance, date=timezone.now())


@receiver(post_save, sender=Topo)
def create_topo(sender, instance, created, **kwargs):
    if created:
        TopoBorrowing.objects.create(item=instance, date=timezone.now())
