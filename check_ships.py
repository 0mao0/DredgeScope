import sqlite3
conn = sqlite3.connect('d:/AI/DredgeScope/backend/data/dredge_intel.db')
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM ships')
print('Total ships:', c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM ships WHERE status IS NOT NULL AND status != ''")
print('Ships with status:', c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM ships WHERE location IS NOT NULL AND location != ''")
print('Ships with location:', c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM ships WHERE location LIKE '%,%'")
print('Ships with lat,lng format:', c.fetchone()[0])

conn.close()
