"""Web采集源"""

from .dredging_contractors import DredgingContractorsSource
from .iadc import IADCSource
from .ceda import CEDASource
from .china_dredging import ChinaDredgingSource
from .cccc_cdc import CCCCDredgingSource
from .cccc_sdc import CCCCSdcSource
from .cccc_gdc import CCCCGdcSource
from .cccc_tdc import CCCCTdcSource
from .jan_de_nul import JanDeNulSource
from .van_oord import VanOordSource
from .boskalis import BoskalisSource
from .deme import DEMESource

__all__ = [
    'DredgingContractorsSource',
    'IADCSource',
    'CEDASource',
    'ChinaDredgingSource',
    'CCCCDredgingSource',
    'CCCCSdcSource',
    'CCCCGdcSource',
    'CCCCTdcSource',
    'JanDeNulSource',
    'VanOordSource',
    'BoskalisSource',
    'DEMESource'
]
