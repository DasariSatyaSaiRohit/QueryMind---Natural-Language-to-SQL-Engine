import { MigrationInterface, QueryRunner, Table } from 'typeorm';

export class CreateRequestLogs1717723300000 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.createTable(
      new Table({
        name: 'request_logs',
        columns: [
          {
            name: 'log_id',
            type: 'uuid',
            isPrimary: true,
            generationStrategy: 'uuid',
            default: 'uuid_generate_v4()',
          },
          { name: 'request_id', type: 'varchar', length: '36' },
          { name: 'correlation_id', type: 'varchar', length: '36' },
          { name: 'user_id', type: 'varchar', length: '36' },
          { name: 'method', type: 'varchar', length: '10' },
          { name: 'path', type: 'varchar', length: '500' },
          { name: 'status_code', type: 'int', default: 0 },
          { name: 'duration_ms', type: 'int', default: 0 },
          { name: 'deleted_at', type: 'timestamp', isNullable: true },
          {
            name: 'timestamp',
            type: 'timestamp',
            default: 'CURRENT_TIMESTAMP',
          },
        ],
        indices: [
          { columnNames: ['user_id'] },
          { columnNames: ['request_id'] },
          { columnNames: ['timestamp'] },
        ],
      }),
      true,
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.dropTable('request_logs');
  }
}
