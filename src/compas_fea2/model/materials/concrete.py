from math import log

from compas_fea2.units import UnitRegistry
from compas_fea2.units import units as u

from .material import _Material


class Concrete(_Material):
    """Elastic and plastic-cracking Eurocode-based concrete material.

    Parameters
    ----------
    fck : float or pint.Quantity
        Characteristic (5%) 28-day cylinder strength. Without ``units`` it is a
        plain number in [MPa]; with ``units`` it is expressed in that unit system
        (e.g. ``20 * units.MPa``).
    E : float, optional
        Young's modulus. If not given, Ecm from Eurocode 2 (eq. 3.5) is used.
    v : float, optional
        Poisson's ratio v [-].
    fr : list, optional
        Failure ratios.
    density : float, optional
        Density of the concrete material [kg/m^3].
    name : str, optional
        Name of the material.
    units : :class:`pint.UnitRegistry` or str, optional
        Unit system of the inputs and of the stored values (e.g. ``"SI"`` or
        ``"SI_mm"``). If omitted, ``fck`` is read in [MPa] and all stored values
        are in SI base units [Pa] (legacy behaviour).

    Attributes
    ----------
    E : float
        Young's modulus E.
    v : float
        Poisson's ratio v.
    G : float
        Shear modulus G.
    fck : float
        Characteristic (5%) 28-day cylinder strength.
    fr : list
        Failure ratios.
    tension : dict
        Parameters for modeling the tension side of the stress-strain curve.
    compression : dict
        Parameters for modeling the compression side of the stress-strain curve.

    Notes
    -----
    The concrete model is based on Eurocode 2 up to fck=90 MPa.
    """

    def __init__(self, *, fck, E=None, v=None, density=None, fr=None, units=None, **kwargs):
        super().__init__(density=density, **kwargs)

        # Eurocode 2 formulas are written in MPa. Work out how many stress units
        # of the target unit system make up 1 MPa, and convert fck to MPa.
        # Note: pint quantities have already been converted to the base units
        # of their registry by the DimensionlessMeta metaclass.
        if units is None:
            mpa = 10**6  # legacy: fck given in MPa, results stored in Pa
            fck_mpa = fck
            self._units_system = None
        else:
            if not isinstance(units, UnitRegistry):
                units = u(system=units)
            mpa = (1 * units.MPa).to_base_units().magnitude
            fck_mpa = fck / mpa
            self._units_system = units.default_system

        if not 0 < fck_mpa <= 90:
            raise ValueError(
                "fck must be between 0 and 90 MPa (Eurocode 2 range), got {} MPa. "
                "Check that fck and units match.".format(fck_mpa)
            )
        fck = fck_mpa

        # Ensure small increment for stress-strain curve
        de = 0.0001

        # Compute material properties based on Eurocode 2 (all in MPa)
        fcm = fck + 8  # Mean compressive strength
        Ecm = 22 * 10**3 * (fcm / 10) ** 0.3  # Young's modulus [MPa]
        ec1 = min(0.7 * fcm**0.31, 2.8) * 0.001  # Strain at peak stress
        ecu1 = 0.0035 if fck < 50 else (2.8 + 27 * ((98 - fcm) / 100.0) ** 4) * 0.001  # Ultimate strain

        # Stress-strain model parameters
        k = 1.05 * Ecm * ec1 / fcm
        e = [i * de for i in range(int(ecu1 / de) + 1)]  # Strain values
        ec = [ei - e[1] for ei in e[1:]] if len(e) > 1 else [0.0]  # Adjusted strain values

        # Tensile strength according to Eurocode 2
        fctm = 0.3 * fck ** (2 / 3) if fck <= 50 else 2.12 * log(1 + fcm / 10)  # Tensile strength
        fc = [mpa * fcm * (k * (ei / ec1) - (ei / ec1) ** 2) / (1 + (k - 2) * (ei / ec1)) for ei in ec]

        ft = [1.0, 0.0]  # Tension stress-strain curve
        et = [0.0, 0.001]  # Corresponding strain values for tension

        fr = fr or [1.16, fctm / fcm]  # Failure ratios default

        # Assign attributes, converted from MPa to the target unit system
        self.E = Ecm * mpa if E is None else E
        self.fck = fck * mpa
        self.fc = kwargs.get("fc", fc)
        self.ec = kwargs.get("ec", ec)
        self.v = v if v is not None else 0.17
        self.ft = kwargs.get("ft", ft)
        self.et = kwargs.get("et", et)
        self.fr = kwargs.get("fr", fr)

        # Ensure valid Young’s modulus calculation
        if len(self.fc) > 1 and self.fc[1] == 0:
            raise ValueError("fc[1] must be non-zero to calculate E.")
        if len(self.ec) > 1 and self.ec[1] == 0:
            raise ValueError("ec[1] must be non-zero for correct calculations.")

        # Tension and compression dictionaries
        self.tension = {"f": self.ft, "e": self.et}
        self.compression = {"f": self.fc[1:], "e": self.ec}

    @property
    def G(self):
        return 0.5 * self.E / (1 + self.v)

    def __str__(self):
        return """
Concrete Material
-----------------
name    : {}
density : {}

E   : {}
v   : {}
G   : {}
fck : {}
fr  : {}
""".format(
            self.name, self.density, self.E, self.v, self.G, self.fck, self.fr
        )

    @property
    def __data__(self):
        data = super().__data__
        data.update(
            {
                "fck": self.fck,
                "E": self.E,
                "v": self.v,
                "fr": self.fr,
                "tension": self.tension,
                "compression": self.compression,
                "units": self._units_system,
            }
        )
        return data

    @classmethod
    def __from_data__(cls, data):
        units = data.get("units")
        fck = data["fck"]
        if units is None:
            # legacy: stored in Pa, but the constructor expects MPa
            fck = fck / 10**6
        return cls(
            fck=fck,
            E=data["E"],
            v=data["v"],
            density=data["density"],
            fr=data["fr"],
            name=data.get("name"),
            units=units,
        )

    # FIXME: this is only working for the basic material properties.
    @classmethod
    def C20_25(cls, units=None, **kwargs):
        """Concrete C20/25 (EN 1992-1-1): fck = 20 MPa (cylinder), fck,cube = 25 MPa.

        Parameters
        ----------
        units : :class:`pint.UnitRegistry` or str, optional
            Unit system, by default ``"SI_mm"``.
        """
        if units is None:
            units = u(system="SI_mm")
        elif not isinstance(units, UnitRegistry):
            units = u(system=units)
        return cls(fck=20 * units.MPa, v=0.17, density=2400 * units("kg/m**3"), name="C20/25", units=units, **kwargs)


class ConcreteSmearedCrack(_Material):
    """Elastic and plastic, cracking concrete material.

    Parameters
    ----------
    E : float
        Young's modulus E.
    v : float
        Poisson's ratio v.
    fc : list
        Plastic stress data in compression.
    ec : list
        Plastic strain data in compression.
    ft : list
        Plastic stress data in tension.
    et : list
        Plastic strain data in tension.
    fr : list, optional
        Failure ratios.
    density : float, optional
        Density of the concrete material [kg/m^3].
    name : str, optional
        Name of the material.

    Attributes
    ----------
    E : float
        Young's modulus E.
    v : float
        Poisson's ratio v.
    G : float
        Shear modulus G.
    fc : list
        Plastic stress data in compression.
    ec : list
        Plastic strain data in compression.
    ft : list
        Plastic stress data in tension.
    et : list
        Plastic strain data in tension.
    fr : list
        Failure ratios.
    tension : dict
        Parameters for modelling the tension side of the stress-strain curve.
    compression : dict
        Parameters for modelling the compression side of the stress-strain curve.
    """

    def __init__(self, *, E, v, density, fc, ec, ft, et, fr=[1.16, 0.0836], **kwargs):
        super().__init__(density=density, **kwargs)

        self.E = E
        self.v = v
        self.fc = fc
        self.ec = ec
        self.ft = ft
        self.et = et
        self.fr = fr
        # are these necessary if we have the above?
        self.tension = {"f": ft, "e": et}
        self.compression = {"f": fc, "e": ec}

    @property
    def G(self):
        return 0.5 * self.E / (1 + self.v)

    def __str__(self):
        return """
Concrete Material
-----------------
name    : {}
density : {}

E  : {}
v  : {}
G  : {}
fc : {}
ec : {}
ft : {}
et : {}
fr : {}
""".format(
            self.name, self.density, self.E, self.v, self.G, self.fc, self.ec, self.ft, self.et, self.fr
        )

    @property
    def __data__(self):
        data = super().__data__
        data.update(
            {
                "class": self.__class__.__name__,
                "E": self.E,
                "v": self.v,
                "fc": self.fc,
                "ec": self.ec,
                "ft": self.ft,
                "et": self.et,
                "fr": self.fr,
                "tension": self.tension,
                "compression": self.compression,
            }
        )
        return data

    @classmethod
    def __from_data__(cls, data):
        return cls(
            E=data["E"],
            v=data["v"],
            density=data["density"],
            fc=data["fc"],
            ec=data["ec"],
            ft=data["ft"],
            et=data["et"],
            fr=data["fr"],
            name=data["name"],
        )


class ConcreteDamagedPlasticity(_Material):
    """Damaged plasticity isotropic and homogeneous material.

    Parameters
    ----------
    E : float
        Young's modulus E.
    v : float
        Poisson's ratio v.
    damage : list
        Damage parameters.
    hardening : list
        Compression hardening parameters.
    stiffening : list
        Tension stiffening parameters.
    density : float, optional
        Density of the concrete material [kg/m^3].
    name : str, optional
        Name of the material.

    Attributes
    ----------
    E : float
        Young's modulus E.
    v : float
        Poisson's ratio v.
    G : float
        Shear modulus G.
    damage : list
        Damage parameters.
    hardening : list
        Compression hardening parameters.
    stiffening : list
        Tension stiffening parameters.
    """

    def __init__(self, *, E, v, density, damage, hardening, stiffening, **kwargs):
        super().__init__(density=density, **kwargs)

        self.E = E
        self.v = v

        # TODO would make sense to validate these inputs
        self.damage = damage
        self.hardening = hardening
        self.stiffening = stiffening

    @property
    def G(self):
        return 0.5 * self.E / (1 + self.v)

    @property
    def __data__(self):
        data = super().__data__
        data.update(
            {
                "class": self.__class__.__name__,
                "E": self.E,
                "v": self.v,
                "damage": self.damage,
                "hardening": self.hardening,
                "stiffening": self.stiffening,
            }
        )
        return data

    @classmethod
    def __from_data__(cls, data):
        return cls(
            E=data["E"],
            v=data["v"],
            density=data["density"],
            damage=data["damage"],
            hardening=data["hardening"],
            stiffening=data["stiffening"],
            name=data["name"],
        )
