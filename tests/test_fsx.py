# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import time
from dateutil.parser import parse as date_parse

import c7n.resources.fsx
from c7n.testing import mock_datetime_now
from .common import BaseTest
import c7n.filters.backup


class TestFSx(BaseTest):
    def test_fsx_resource(self):
        session_factory = self.replay_flight_data('test_fsx_resource')
        p = self.load_policy(
            {
                'name': 'test-fsx',
                'resource': 'fsx',
                'filters': [
                    {
                        'tag:Name': 'test'
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertTrue(len(resources))

    def test_fsx_tag_resource(self):
        session_factory = self.replay_flight_data('test_fsx_tag_resource')
        p = self.load_policy(
            {
                'name': 'test-fsx',
                'resource': 'fsx',
                'filters': [
                    {
                        'tag:Name': 'test'
                    }
                ],
                'actions': [
                    {
                        'type': 'tag',
                        'key': 'test',
                        'value': 'test-value'
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertTrue(len(resources))
        client = session_factory().client('fsx')
        tags = client.list_tags_for_resource(ResourceARN=resources[0]['ResourceARN'])

        self.assertTrue([t for t in tags['Tags'] if t['Key'] == 'test'])

    def test_fsx_remove_tag_resource(self):
        session_factory = self.replay_flight_data('test_fsx_remove_tag_resource')
        p = self.load_policy(
            {
                'name': 'test-fsx',
                'resource': 'fsx',
                'filters': [
                    {
                        'tag:Name': 'test'
                    }
                ],
                'actions': [
                    {
                        'type': 'remove-tag',
                        'tags': [
                            'maid_status',
                            'test'
                        ],
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertTrue(len(resources))
        client = session_factory().client('fsx')
        tags = client.list_tags_for_resource(ResourceARN=resources[0]['ResourceARN'])

        self.assertFalse([t for t in tags['Tags'] if t['Key'] != 'Name'])

    def test_fsx_mark_for_op_resource(self):
        session_factory = self.replay_flight_data('test_fsx_mark_for_op_resource')
        p = self.load_policy(
            {
                'name': 'test-fsx',
                'resource': 'fsx',
                'filters': [
                    {
                        'tag:Name': 'test'
                    }
                ],
                'actions': [
                    {
                        'type': 'mark-for-op',
                        'op': 'tag'
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertTrue(len(resources))
        client = session_factory().client('fsx')
        tags = client.list_tags_for_resource(ResourceARN=resources[0]['ResourceARN'])

        self.assertTrue([t for t in tags['Tags'] if t['Key'] == 'maid_status'])

    def test_fsx_update_configuration(self):
        session_factory = self.replay_flight_data('test_fsx_update_configuration')
        p = self.load_policy(
            {
                'name': 'test-update-fsx-configuration',
                'resource': 'fsx',
                'filters': [
                    {
                        'WindowsConfiguration.AutomaticBackupRetentionDays': 1
                    }
                ],
                'actions': [
                    {
                        'type': 'update',
                        'WindowsConfiguration': {
                            'AutomaticBackupRetentionDays': 3
                        }
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()

        self.assertEqual(len(resources), 1)
        client = session_factory().client('fsx')
        new_resources = client.describe_file_systems()['FileSystems']
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            new_resources[0]['FileSystemId'],
            resources[0]['FileSystemId']
        )
        self.assertEqual(
            new_resources[0]['WindowsConfiguration']['AutomaticBackupRetentionDays'], 3)

    def test_fsx_create_bad_backup(self):
        session_factory = self.replay_flight_data('test_fsx_create_backup_with_errors')
        p = self.load_policy(
            {
                'name': 'test-update-fsx-configuration',
                'resource': 'fsx',
                'filters': [
                    {
                        'FileSystemId': 'fs-0bc98cbfb6b356896'
                    }
                ],
                'actions': [
                    {
                        'type': 'backup',
                        'tags': {
                            'test-tag': 'backup-tag'
                        }
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()

        self.assertEqual(len(resources), 1)

        client = session_factory().client('fsx')

        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': ['fs-0bc98cbfb6b356896']
                },
                {
                    'Name': 'backup-type',
                    'Values': ['USER_INITIATED']
                }
            ]
        )
        self.assertEqual(len(backups['Backups']), 0)

    def test_fsx_create_backup(self):
        session_factory = self.replay_flight_data('test_fsx_create_backup')
        p = self.load_policy(
            {
                'name': 'test-update-fsx-configuration',
                'resource': 'fsx',
                'filters': [
                    {
                        'FileSystemId': 'fs-002ccbccdcf032728'
                    }
                ],
                'actions': [
                    {
                        'type': 'backup',
                        'copy-tags': True,
                        'tags': {
                            'test-tag': 'backup-tag'
                        }
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()

        self.assertEqual(len(resources), 1)

        client = session_factory().client('fsx')

        if self.recording:
            time.sleep(500)

        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': ['fs-002ccbccdcf032728']
                },
                {
                    'Name': 'backup-type',
                    'Values': ['USER_INITIATED']
                }
            ]
        )

        self.assertEqual(len(backups['Backups']), 1)

        expected_tags = resources[0]['Tags']

        expected_tags.append({'Key': 'test-tag', 'Value': 'backup-tag'})
        expected_tag_map = {t['Key']: t['Value'] for t in expected_tags}
        final_tag_map = {t['Key']: t['Value'] for t in backups['Backups'][0]['Tags']}

        self.assertEqual(expected_tag_map, final_tag_map)

    def test_fsx_create_backup_without_copy_tags(self):
        session_factory = self.replay_flight_data('test_fsx_create_backup_without_copy_tags')
        p = self.load_policy(
            {
                'name': 'test-update-fsx-configuration',
                'resource': 'fsx',
                'filters': [
                    {
                        'FileSystemId': 'fs-002ccbccdcf032728'
                    }
                ],
                'actions': [
                    {
                        'type': 'backup',
                        'copy-tags': False,
                        'tags': {
                            'test-tag': 'backup-tag'
                        }
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

        if self.recording:
            time.sleep(500)

        client = session_factory().client('fsx')
        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': ['fs-002ccbccdcf032728']
                },
                {
                    'Name': 'backup-type',
                    'Values': ['USER_INITIATED']
                }
            ]
        )
        self.assertEqual(len(backups['Backups']), 1)
        expected_tags = [{'Key': 'test-tag', 'Value': 'backup-tag'}]
        self.assertEqual(expected_tags, backups['Backups'][0]['Tags'])

    def test_fsx_delete_file_system_skip_snapshot(self):
        session_factory = self.replay_flight_data('test_fsx_delete_file_system_skip_snapshot')
        p = self.load_policy(
            {
                'name': 'fsx-delete-file-system',
                'resource': 'fsx',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'Lifecycle',
                        'value': 'AVAILABLE'
                    }
                ],
                'actions': [
                    {
                        'type': 'delete',
                        'skip-snapshot': True
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        client = session_factory().client('fsx')
        fs = client.describe_file_systems(
            FileSystemIds=[resources[0]['FileSystemId']])['FileSystems']
        self.assertTrue(len(fs), 1)
        self.assertEqual(fs[0]['Lifecycle'], 'DELETING')
        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': [fs[0]['FileSystemId']]
                },
                {
                    'Name': 'backup-type',
                    'Values': ['USER_INITIATED']
                }
            ]
        )['Backups']
        self.assertEqual(len(backups), 0)

    def test_fsx_delete_file_system(self):
        session_factory = self.replay_flight_data('test_fsx_delete_file_system')
        p = self.load_policy(
            {
                'name': 'fsx-delete-file-system',
                'resource': 'fsx',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'Lifecycle',
                        'value': 'AVAILABLE'
                    }
                ],
                'actions': [
                    {
                        'type': 'delete',
                        'tags': {
                            'DeletedBy': 'CloudCustodian'
                        },
                        'skip-snapshot': False
                    }
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        client = session_factory().client('fsx')
        fs = client.describe_file_systems(
            FileSystemIds=[resources[0]['FileSystemId']])['FileSystems']
        self.assertTrue(len(fs), 1)
        self.assertEqual(fs[0]['Lifecycle'], 'DELETING')
        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': [fs[0]['FileSystemId']]
                },
                {
                    'Name': 'backup-type',
                    'Values': ['USER_INITIATED']
                }
            ]
        )['Backups']
        self.assertEqual(len(backups), 1)

    def test_fsx_delete_file_system_with_error(self):
        session_factory = self.replay_flight_data('test_fsx_delete_file_system_with_error')
        p = self.load_policy(
            {
                'name': 'fsx-delete-file-system',
                'resource': 'fsx',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'Lifecycle',
                        'value': 'CREATING'
                    }
                ],
                'actions': [
                    {'type': 'delete'}
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        client = session_factory().client('fsx')
        fs = client.describe_file_systems(
            FileSystemIds=[resources[0]['FileSystemId']])['FileSystems']
        self.assertTrue(len(fs), 1)
        self.assertNotEqual(fs[0]['Lifecycle'], 'DELETING')

    def test_fsx_arn_in_event(self):
        session_factory = self.replay_flight_data('test_fsx_resource')
        p = self.load_policy({'name': 'test-fsx', 'resource': 'fsx'},
            session_factory=session_factory)
        resources = p.resource_manager.get_resources(
            ["arn:aws:fsx:us-east-1:644160558196:file-system/fs-0bc98cbfb6b356896"])
        self.assertEqual(len(resources), 1)

    def test_fsx_backup_count_filter(self):
        session_factory = self.replay_flight_data("test_fsx_backup_count_filter")
        p = self.load_policy(
            {
                "name": "fsx-backup-count-filter",
                "resource": "fsx",
                "filters": [{"type": "consecutive-backups", "days": 2}],
            },
            config={'region': 'us-west-2'},
            session_factory=session_factory,
        )
        with mock_datetime_now(date_parse("2022-07-04"), c7n.resources.fsx):
            resources = p.run()
        self.assertEqual(len(resources), 3)

    def test_fsx_igw_subnet(self):
        factory = self.replay_flight_data('test_fsx_public_subnet')
        p = self.load_policy({
            'name': 'fsx-public',
            'resource': 'fsx',
            'filters': [
                {'type': 'subnet',
                 'key': 'SubnetId',
                 'value': 'present',
                 'igw': True}
            ]}, config={'region': 'us-west-2'}, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_fsx_consecutive_aws_backups_count_filter(self):
        session_factory = self.replay_flight_data("test_fsx_consecutive_aws_backups_count_filter")
        p = self.load_policy(
            {
                "name": "fsx_consecutive_aws_backups_count_filter",
                "resource": "fsx",
                "filters": [
                    {
                        "type": "consecutive-aws-backups",
                        "count": 2,
                        "period": "days",
                        "status": "COMPLETED"
                    }
                ]
            },
            session_factory=session_factory,
        )
        with mock_datetime_now(date_parse("2022-09-09T00:00:00+00:00"), c7n.filters.backup):
            resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_fsx_volumes_filter(self):
        session_factory = self.replay_flight_data("test_fsx_volumes_filter")
        p = self.load_policy({
            "name": "fsx_volumes_filter",
            "resource": "aws.fsx",
            "filters": [{
                "type": "volume",
                "attrs": []
            }]
        }, session_factory=session_factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(len(resources[0]['c7n:Volumes']), 2)

    def test_fsx_vpc_filter(self):
        session_factory = self.replay_flight_data("test_fsx_vpc_filter")
        p = self.load_policy({
            "name": "fsx_vpc_filter",
            "resource": "aws.fsx",
            "filters": [{
                "type": "vpc",
                "key": "IsDefault",
                "value": True
            }]
        }, session_factory=session_factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(len(resources[0]['c7n:matched-vpcs']), 1)


class TestFSxVolume(BaseTest):
    def test_fsx_volume_query(self):
        session_factory = self.replay_flight_data('test_fsx_volume_query')
        p = self.load_policy(
            {
                "name": "fsx_volume_query",
                "resource": "aws.fsx-volume",
                "filters": [{
                    "type": "value",
                    "key": "Lifecycle",
                    "value": "AVAILABLE"
                }]
            },
            session_factory=session_factory,
        )

        resources = p.run()
        self.assertEqual(len(resources), 1)


class TestFSxBackup(BaseTest):
    def test_fsx_backup_delete(self):
        session_factory = self.replay_flight_data('test_fsx_backup_delete')
        backup_id = 'backup-0d1fb25003287b260'
        p = self.load_policy(
            {
                'name': 'fsx-backup-resource',
                'resource': 'fsx-backup',
                'filters': [
                    {'BackupId': backup_id}
                ],
                'actions': [
                    {'type': 'delete'}
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertTrue(resources)
        client = session_factory().client('fsx')
        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': ['fs-002ccbccdcf032728']
                }
            ]
        )['Backups']
        results = [b for b in backups if b['BackupId'] == backup_id]
        self.assertFalse(results)

    def test_fsx_backup_tag(self):
        session_factory = self.replay_flight_data('test_fsx_backup_tag')
        backup_id = 'backup-0b644cd380298f720'
        p = self.load_policy(
            {
                'name': 'fsx-backup-resource-tag',
                'resource': 'fsx-backup',
                'filters': [
                    {'BackupId': backup_id},
                    {'Tags': []}
                ],
                'actions': [
                    {'type': 'tag', 'tags': {'tag-test': 'tag-test'}}
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        client = session_factory().client('fsx')
        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': ['fs-002ccbccdcf032728']
                }
            ]
        )['Backups']
        tags = None
        for b in backups:
            if b['BackupId'] == backup_id:
                self.assertTrue(len(b['Tags']), 1)
                tags = b['Tags']
        self.assertTrue(tags)
        self.assertEqual(tags[0]['Key'], 'tag-test')
        self.assertEqual(tags[0]['Value'], 'tag-test')

    def test_fsx_backup_mark_for_op(self):
        session_factory = self.replay_flight_data('test_fsx_backup_mark_for_op')
        backup_id = 'backup-09d3dfca849cfc629'
        p = self.load_policy(
            {
                'name': 'fsx-backup-resource-mark-for-op',
                'resource': 'fsx-backup',
                'filters': [
                    {'BackupId': backup_id},
                    {'Tags': []}
                ],
                'actions': [
                    {'type': 'mark-for-op', 'op': 'delete'}
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

        client = session_factory().client('fsx')
        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': ['fs-002ccbccdcf032728']
                }
            ]
        )['Backups']
        tags = None
        for b in backups:
            if b['BackupId'] == backup_id:
                self.assertTrue(len(b['Tags']), 1)
                tags = [t for t in b['Tags'] if t['Key'] == 'maid_status']
        self.assertTrue(tags)

    def test_fsx_backup_remove_tag(self):
        session_factory = self.replay_flight_data('test_fsx_backup_remove_tag')
        backup_id = 'backup-05c81253149962783'
        p = self.load_policy(
            {
                'name': 'fsx-backup-resource-remove-tag',
                'resource': 'fsx-backup',
                'filters': [
                    {'BackupId': backup_id},
                    {'tag:test-tag': 'backup-tag'},
                ],
                'actions': [
                    {'type': 'remove-tag', 'tags': ['test-tag']}
                ]
            },
            session_factory=session_factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

        client = session_factory().client('fsx')
        backups = client.describe_backups(
            Filters=[
                {
                    'Name': 'file-system-id',
                    'Values': ['fs-002ccbccdcf032728']
                }
            ]
        )['Backups']
        tags = [1]
        for b in backups:
            if b['BackupId'] == backup_id:
                if len(b['Tags']) == 0:
                    tags = b['Tags']
        self.assertEqual(len(tags), 0)

    def test_kms_key_filter(self):
        session_factory = self.replay_flight_data("test_fsx_kms_key_filter")
        p = self.load_policy(
            {
                "name": "fsx-kms-key-filters",
                "resource": "fsx",
                "filters": [
                    {
                        "type": "kms-key",
                        "key": "c7n:AliasName",
                        "value": "^(alias/aws/fsx)",
                        "op": "regex"
                    }
                ]
            },
            session_factory=session_factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(len(resources[0]['c7n:matched-kms-key']), 1)

    def test_kms_key_filter_fsx_backup(self):
        session_factory = self.replay_flight_data("test_kms_key_filter_fsx_backup")
        p = self.load_policy(
            {
                "name": "kms_key_filter_fsx_backup",
                "resource": "fsx-backup",
                "filters": [
                    {
                        "type": "kms-key",
                        "key": "c7n:AliasName",
                        "value": "^(alias/aws/fsx)",
                        "op": "regex"
                    }
                ]
            },
            session_factory=session_factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 3)
        for r in resources:
            self.assertEqual(len(r['c7n:matched-kms-key']), 1)
