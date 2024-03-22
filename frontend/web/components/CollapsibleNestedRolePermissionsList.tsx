import React, {
  useState,
  forwardRef,
  useImperativeHandle,
  Ref,
  FC,
} from 'react'
import Icon from './Icon'
import { EditPermissionsModal } from './EditPermissions'
import {
  useGetRoleProjectPermissionsQuery,
  useGetRoleEnvironmentPermissionsQuery,
} from 'common/services/useRolePermission'
import Format from 'common/utils/format'
import { PermissionLevel, Req } from 'common/types/requests'
import { Role } from 'common/types/responses'

type NameAndId = {
  name: string
  id: number | string
  [key: string]: any
}

type CollapsibleNestedRolePermissionsListProps = {
  mainItems: NameAndId[]
  role: Role
  ref?: Ref<any>
  level: string
  filter: string
}

export type PermissionsSummaryType = {
  level: PermissionLevel
  levelId: number
  role: Role | null
}
const PermissionsSummary: FC<PermissionsSummaryType> = ({
  level,
  levelId,
  role,
}) => {
  const { data: projectPermissions, isLoading: projectIsLoading } =
    useGetRoleProjectPermissionsQuery(
      {
        organisation_id: role?.organisation,
        project_id: levelId,
        role_id: role?.id,
      },
      { skip: !levelId || level == 'project' },
    )

  const { data: envPermissions, isLoading: envIsLoading } =
    useGetRoleEnvironmentPermissionsQuery(
      {
        env_id: levelId,
        organisation_id: role?.organisation,
        role_id: role?.id,
      },
      { skip: !levelId || level !== 'environment' },
    )

  const permissions = projectPermissions || envPermissions
  const roleResult = permissions?.results.filter(
    (item) => item.role === role?.id,
  )
  const roleRermissions =
    roleResult && roleResult.length > 0 ? roleResult[0].permissions : []

  const isAdmin =
    roleResult && roleResult.length > 0 ? roleResult[0].admin : false

  const permissionsSummary =
    (roleRermissions &&
      roleRermissions.length > 0 &&
      roleRermissions
        .map((item: string) => Format.enumeration.get(item))
        .join(', ')) ||
    ''

  return projectIsLoading || envIsLoading ? (
    <div className='modal-body text-center'>
      <Loader />
    </div>
  ) : (
    <div>{isAdmin ? 'Administrator' : permissionsSummary}</div>
  )
}

const CollapsibleNestedRolePermissionsList: React.FC<CollapsibleNestedRolePermissionsListProps> =
  forwardRef(({ filter, level, mainItems, role }, ref) => {
    const [expandedItems, setExpandedItems] = useState<string[]>([])
    const [unsavedProjects, setUnsavedProjects] = useState<string[]>([])

    const mainItemsFiltered =
      mainItems &&
      mainItems?.filter((v) => {
        const search = filter.toLowerCase()
        if (!search) return true
        return `${v.name}`.toLowerCase().includes(search)
      })

    const toggleExpand = (id: string) => {
      setExpandedItems((prevExpanded) =>
        prevExpanded.includes(id)
          ? prevExpanded.filter((item) => item !== id)
          : [...prevExpanded, id],
      )
    }

    const removeUnsavedProject = (projectId) => {
      setUnsavedProjects((prevUnsavedProjects) =>
        prevUnsavedProjects.filter((id) => id !== projectId),
      )
    }

    useImperativeHandle(
      ref,
      () => {
        return {
          onClosing() {
            if (unsavedProjects.length > 0) {
              return new Promise((resolve) => {
                openConfirm({
                  body: 'Closing this will discard your unsaved changes.',
                  noText: 'Cancel',
                  onNo: () => resolve(false),
                  onYes: () => resolve(true),
                  title: 'Discard changes',
                  yesText: 'Ok',
                })
              })
            } else {
              return Promise.resolve(true)
            }
          },
          tabChanged() {
            return unsavedProjects.length > 0
          },
        }
      },
      [unsavedProjects],
    )

    return (
      <div className='collapsible-nested-list list-container'>
        {mainItemsFiltered?.map((mainItem, index) => (
          <div key={index}>
            <Row
              key={index}
              onClick={() => toggleExpand(mainItem.id)}
              className='clickable cursor-pointer list-item-sm px-3 list-row'
            >
              <Flex>
                <div className={'list-item-subtitle'}>
                  <strong>{mainItem.name}</strong>{' '}
                  {unsavedProjects.includes(mainItem.id) && (
                    <div className='unread'>Unsaved</div>
                  )}
                </div>
              </Flex>
              <Flex>
                <div className={'list-item-subtitle'}>
                  <PermissionsSummary
                    level={level}
                    levelId={mainItem.id}
                    role={role}
                  />
                </div>
              </Flex>
              <Icon
                name={
                  expandedItems.includes(mainItem.id)
                    ? 'chevron-down'
                    : 'chevron-right'
                }
                width={25}
              />
            </Row>
            <div>
              {expandedItems.includes(mainItem.id) && (
                <EditPermissionsModal
                  id={mainItem.id}
                  level={level}
                  role={role}
                  permissionChanged={() => {
                    if (!unsavedProjects.includes(mainItem.id)) {
                      setUnsavedProjects((prevUnsavedProjects) => [
                        ...prevUnsavedProjects,
                        mainItem.id,
                      ])
                    }
                  }}
                  onSave={() => removeUnsavedProject(mainItem.id)}
                />
              )}
            </div>
          </div>
        ))}
      </div>
    )
  })

export default CollapsibleNestedRolePermissionsList
