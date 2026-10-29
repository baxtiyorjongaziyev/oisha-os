"""Creates 'Mening Bitimlarim' (Kanban & Table) and 'Mening Kompaniyalarim' views in Twenty CRM,
with auto-filter: isCurrentWorkspaceMemberSelected = true.
Also creates per-seller views for Admin overview.
"""
import subprocess
import uuid

def run_psql(sql: str) -> str:
    p = subprocess.Popen(
        ["docker", "exec", "-i", "twenty-db-1", "psql", "-U", "postgres", "-d", "default"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate(sql.encode())
    if p.returncode != 0:
        raise RuntimeError(f"PSQL Error: {err.decode()}")
    return out.decode()

WORKSPACE_ID = "da90a5c2-0152-4cf2-b95b-b73b47100f3d"
APP_ID = "6ef960a1-c5ad-4c5b-9df0-2988685d15bc"

OPP_OBJ_ID = "2b89f0eb-93f9-43bb-b175-7806f2e4935e"
COMP_OBJ_ID = "13d64181-bcf2-4b55-bb27-d8818a7630c0"

OPP_OWNER_FIELD_ID = "5b9a5fbc-8ba3-42d3-a346-402a28b51d25"
COMP_OWNER_FIELD_ID = "ca167af2-80f6-4c1f-a5e9-4a8b14664bd8"

OPP_STAGE_FIELD_ID = "ba30175e-f7bb-4c00-9744-6c6938d23425"
OPP_AMOUNT_FIELD_ID = "5ae1734c-25f1-446c-8c02-987a63e934ea"

BASE_KANBAN_VIEW_ID = "9f3bc592-b0a0-4b5e-b4dd-c33fb5833f58"
BASE_COMP_VIEW_ID = "3c8e076a-a6f5-4ced-bd87-8446ef4c78a4"
BASE_OPP_TABLE_ID = "1ac3d2dd-eb40-45a5-8237-35f218eb96ed"

sql_commands = []

# 1. Update existing views positions and names for clarity
sql_commands.append(f"""
UPDATE core."view" SET name = 'Barcha Bitimlar (Barchasini ko''rish)', position = 2 WHERE id = '{BASE_KANBAN_VIEW_ID}';
UPDATE core."view" SET name = 'Barcha Bitimlar (Jadval)', position = 3 WHERE id = '{BASE_OPP_TABLE_ID}';
UPDATE core."view" SET name = 'Barcha Kompaniyalar (Barchasini ko''rish)', position = 2 WHERE id = '{BASE_COMP_VIEW_ID}';
""")

# 2. Create 'Mening Bitimlarim (Kanban)' as position 0 (Default view)
my_opp_kanban_id = str(uuid.uuid4())
my_opp_kanban_filter_id = str(uuid.uuid4())
my_opp_kanban_univ = str(uuid.uuid4())
my_opp_kanban_f_univ = str(uuid.uuid4())

sql_commands.append(f"""
INSERT INTO core."view" (
    id, "universalIdentifier", name, "objectMetadataId", type, icon, position,
    "isCompact", "isCustom", "openRecordIn", "kanbanAggregateOperation",
    "kanbanAggregateOperationFieldMetadataId", "workspaceId", "createdAt", "updatedAt",
    "applicationId", visibility, "mainGroupByFieldMetadataId", "shouldHideEmptyGroups",
    "isActive", "isSystemSideEffect", "groupLoadLimit"
) VALUES (
    '{my_opp_kanban_id}', '{my_opp_kanban_univ}', 'Mening Bitimlarim (Kanban)', '{OPP_OBJ_ID}', 'KANBAN', 'IconLayoutKanban', 0,
    false, false, 'SIDE_PANEL', 'SUM',
    '{OPP_AMOUNT_FIELD_ID}', '{WORKSPACE_ID}', NOW(), NOW(),
    '{APP_ID}', 'WORKSPACE', '{OPP_STAGE_FIELD_ID}', false,
    true, false, 8
) ON CONFLICT (id) DO NOTHING;

INSERT INTO core."viewFilter" (
    id, "universalIdentifier", "fieldMetadataId", operand, value, "viewId", "workspaceId",
    "createdAt", "updatedAt", "applicationId"
) VALUES (
    '{my_opp_kanban_filter_id}', '{my_opp_kanban_f_univ}', '{OPP_OWNER_FIELD_ID}', 'IS',
    '{{"isCurrentWorkspaceMemberSelected":true,"selectedRecordIds":[]}}',
    '{my_opp_kanban_id}', '{WORKSPACE_ID}', NOW(), NOW(), '{APP_ID}'
) ON CONFLICT (id) DO NOTHING;
""")

# Copy viewFields from BASE_KANBAN_VIEW_ID to my_opp_kanban_id
sql_commands.append(f"""
INSERT INTO core."viewField" (
    id, "universalIdentifier", "fieldMetadataId", position, "isVisible", size, "viewId",
    "workspaceId", "createdAt", "updatedAt", "applicationId"
)
SELECT gen_random_uuid(), gen_random_uuid(), "fieldMetadataId", position, "isVisible", size, '{my_opp_kanban_id}',
       '{WORKSPACE_ID}', NOW(), NOW(), '{APP_ID}'
FROM core."viewField"
WHERE "viewId" = '{BASE_KANBAN_VIEW_ID}';
""")

# 3. Create 'Mening Bitimlarim (Jadval)' as position 1
my_opp_table_id = str(uuid.uuid4())
my_opp_table_filter_id = str(uuid.uuid4())
my_opp_table_univ = str(uuid.uuid4())
my_opp_table_f_univ = str(uuid.uuid4())

sql_commands.append(f"""
INSERT INTO core."view" (
    id, "universalIdentifier", name, "objectMetadataId", type, icon, position,
    "isCompact", "isCustom", "openRecordIn", "workspaceId", "createdAt", "updatedAt",
    "applicationId", visibility, "isActive", "isSystemSideEffect"
) VALUES (
    '{my_opp_table_id}', '{my_opp_table_univ}', 'Mening Bitimlarim (Jadval)', '{OPP_OBJ_ID}', 'TABLE', 'IconTable', 1,
    false, false, 'SIDE_PANEL', '{WORKSPACE_ID}', NOW(), NOW(),
    '{APP_ID}', 'WORKSPACE', true, false
) ON CONFLICT (id) DO NOTHING;

INSERT INTO core."viewFilter" (
    id, "universalIdentifier", "fieldMetadataId", operand, value, "viewId", "workspaceId",
    "createdAt", "updatedAt", "applicationId"
) VALUES (
    '{my_opp_table_filter_id}', '{my_opp_table_f_univ}', '{OPP_OWNER_FIELD_ID}', 'IS',
    '{{"isCurrentWorkspaceMemberSelected":true,"selectedRecordIds":[]}}',
    '{my_opp_table_id}', '{WORKSPACE_ID}', NOW(), NOW(), '{APP_ID}'
) ON CONFLICT (id) DO NOTHING;
""")

sql_commands.append(f"""
INSERT INTO core."viewField" (
    id, "universalIdentifier", "fieldMetadataId", position, "isVisible", size, "viewId",
    "workspaceId", "createdAt", "updatedAt", "applicationId"
)
SELECT gen_random_uuid(), gen_random_uuid(), "fieldMetadataId", position, "isVisible", size, '{my_opp_table_id}',
       '{WORKSPACE_ID}', NOW(), NOW(), '{APP_ID}'
FROM core."viewField"
WHERE "viewId" = '{BASE_OPP_TABLE_ID}';
""")

# 4. Create 'Mening Kompaniyalarim' as position 0 for Company
my_comp_id = str(uuid.uuid4())
my_comp_filter_id = str(uuid.uuid4())
my_comp_univ = str(uuid.uuid4())
my_comp_f_univ = str(uuid.uuid4())

sql_commands.append(f"""
INSERT INTO core."view" (
    id, "universalIdentifier", name, "objectMetadataId", type, icon, position,
    "isCompact", "isCustom", "openRecordIn", "workspaceId", "createdAt", "updatedAt",
    "applicationId", visibility, "isActive", "isSystemSideEffect"
) VALUES (
    '{my_comp_id}', '{my_comp_univ}', 'Mening Kompaniyalarim', '{COMP_OBJ_ID}', 'TABLE', 'IconBuildingSkyscraper', 0,
    false, false, 'SIDE_PANEL', '{WORKSPACE_ID}', NOW(), NOW(),
    '{APP_ID}', 'WORKSPACE', true, false
) ON CONFLICT (id) DO NOTHING;

INSERT INTO core."viewFilter" (
    id, "universalIdentifier", "fieldMetadataId", operand, value, "viewId", "workspaceId",
    "createdAt", "updatedAt", "applicationId"
) VALUES (
    '{my_comp_filter_id}', '{my_comp_f_univ}', '{COMP_OWNER_FIELD_ID}', 'IS',
    '{{"isCurrentWorkspaceMemberSelected":true,"selectedRecordIds":[]}}',
    '{my_comp_id}', '{WORKSPACE_ID}', NOW(), NOW(), '{APP_ID}'
) ON CONFLICT (id) DO NOTHING;
""")

sql_commands.append(f"""
INSERT INTO core."viewField" (
    id, "universalIdentifier", "fieldMetadataId", position, "isVisible", size, "viewId",
    "workspaceId", "createdAt", "updatedAt", "applicationId"
)
SELECT gen_random_uuid(), gen_random_uuid(), "fieldMetadataId", position, "isVisible", size, '{my_comp_id}',
       '{WORKSPACE_ID}', NOW(), NOW(), '{APP_ID}'
FROM core."viewField"
WHERE "viewId" = '{BASE_COMP_VIEW_ID}';
""")

full_sql = "\n".join(sql_commands)
print("Executing SQL batch...")
out = run_psql(full_sql)
print("Result:\n", out)
