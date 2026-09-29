enum AppRole { admin, pastor, leader }

extension AppRoleValue on AppRole {
  String get apiValue => switch (this) {
        AppRole.admin => 'ADMIN',
        AppRole.pastor => 'PASTOR',
        AppRole.leader => 'LIDER',
      };

  static AppRole parse(Object? value) => switch (value) {
        'ADMIN' => AppRole.admin,
        'PASTOR' => AppRole.pastor,
        'LIDER' => AppRole.leader,
        _ => throw FormatException('Rol no compatible: $value'),
      };
}

class CurrentAccount {
  const CurrentAccount({
    required this.id,
    required this.email,
    required this.role,
    required this.active,
    this.districtId,
    this.churchId,
  });

  final String id;
  final String email;
  final AppRole role;
  final bool active;
  final String? districtId;
  final String? churchId;

  factory CurrentAccount.fromJson(Map<String, dynamic> json) => CurrentAccount(
        id: json['id'] as String,
        email: json['email'] as String,
        role: AppRoleValue.parse(json['role']),
        active: json['active'] as bool,
        districtId: json['district_id'] as String?,
        churchId: json['church_id'] as String?,
      );
}

class District {
  const District({required this.id, required this.name});

  final String id;
  final String name;

  factory District.fromJson(Map<String, dynamic> json) =>
      District(id: json['id'] as String, name: json['name'] as String);
}

class Church {
  const Church({
    required this.id,
    required this.districtId,
    required this.name,
    required this.active,
    this.address,
  });

  final String id;
  final String districtId;
  final String name;
  final String? address;
  final bool active;

  factory Church.fromJson(Map<String, dynamic> json) => Church(
        id: json['id'] as String,
        districtId: json['district_id'] as String,
        name: json['name'] as String,
        address: json['address'] as String?,
        active: json['active'] as bool,
      );
}

class OperatorProfile {
  const OperatorProfile({
    required this.id,
    required this.name,
    required this.surname,
    required this.email,
    required this.role,
    required this.active,
    required this.districtId,
    required this.churchId,
    this.phone,
    this.address,
    this.isPrimaryPastor = false,
  });

  final String id;
  final String name;
  final String surname;
  final String email;
  final String role;
  final bool active;
  final String districtId;
  final String churchId;
  final String? phone;
  final String? address;
  final bool isPrimaryPastor;

  String get fullName => '$name $surname';

  factory OperatorProfile.fromJson(Map<String, dynamic> json) =>
      OperatorProfile(
        id: json['id'] as String,
        name: json['name'] as String,
        surname: json['surname'] as String,
        email: json['email'] as String,
        role: json['role'] as String,
        active: json['active'] as bool,
        districtId: json['district_id'] as String,
        churchId: json['church_id'] as String,
        phone: json['phone'] as String?,
        address: json['address'] as String?,
        isPrimaryPastor: json['is_primary_pastor'] as bool? ?? false,
      );
}

class Brother {
  const Brother({
    required this.id,
    required this.name,
    required this.surname,
    required this.phone,
    required this.address,
    required this.districtId,
    required this.churchId,
    required this.leaderId,
    required this.active,
  });

  final String id;
  final String name;
  final String surname;
  final String phone;
  final String address;
  final String districtId;
  final String churchId;
  final String leaderId;
  final bool active;

  String get fullName => '$name $surname';

  factory Brother.fromJson(Map<String, dynamic> json) => Brother(
        id: json['id'] as String,
        name: json['name'] as String,
        surname: json['surname'] as String,
        phone: json['phone'] as String,
        address: json['address'] as String,
        districtId: json['district_id'] as String,
        churchId: json['church_id'] as String,
        leaderId: json['leader_id'] as String,
        active: json['active'] as bool,
      );
}

class Visit {
  const Visit({
    required this.id,
    required this.brotherId,
    required this.leaderId,
    required this.visitType,
    required this.scheduledAt,
    required this.durationMinutes,
    required this.location,
    required this.observations,
    required this.status,
    this.completedAt,
    this.cancellationReason,
  });

  final String id;
  final String brotherId;
  final String leaderId;
  final String visitType;
  final DateTime scheduledAt;
  final DateTime? completedAt;
  final int durationMinutes;
  final String location;
  final String observations;
  final String status;
  final String? cancellationReason;

  factory Visit.fromJson(Map<String, dynamic> json) => Visit(
        id: json['id'] as String,
        brotherId: json['brother_id'] as String,
        leaderId: json['leader_id'] as String,
        visitType: json['visit_type'] as String,
        scheduledAt: DateTime.parse(json['scheduled_at'] as String),
        completedAt: json['completed_at'] == null
            ? null
            : DateTime.parse(json['completed_at'] as String),
        durationMinutes: json['duration_minutes'] as int,
        location: json['location'] as String,
        observations: json['observations'] as String,
        status: json['status'] as String,
        cancellationReason: json['cancellation_reason'] as String?,
      );
}

class VisitHistoryEntry {
  const VisitHistoryEntry({
    required this.id,
    required this.visitId,
    required this.actorId,
    required this.action,
    required this.createdAt,
    this.previousStatus,
    this.newStatus,
    this.previousScheduledAt,
    this.newScheduledAt,
    this.previousValues,
    this.newValues,
    this.reason,
  });

  final String id;
  final String visitId;
  final String actorId;
  final String action;
  final String? previousStatus;
  final String? newStatus;
  final DateTime? previousScheduledAt;
  final DateTime? newScheduledAt;
  final Map<String, dynamic>? previousValues;
  final Map<String, dynamic>? newValues;
  final String? reason;
  final DateTime createdAt;

  factory VisitHistoryEntry.fromJson(Map<String, dynamic> json) =>
      VisitHistoryEntry(
        id: json['id'] as String,
        visitId: json['visit_id'] as String,
        actorId: json['actor_id'] as String,
        action: json['action'] as String,
        previousStatus: json['previous_status'] as String?,
        newStatus: json['new_status'] as String?,
        previousScheduledAt: json['previous_scheduled_at'] == null
            ? null
            : DateTime.parse(json['previous_scheduled_at'] as String),
        newScheduledAt: json['new_scheduled_at'] == null
            ? null
            : DateTime.parse(json['new_scheduled_at'] as String),
        previousValues: json['previous_values'] as Map<String, dynamic>?,
        newValues: json['new_values'] as Map<String, dynamic>?,
        reason: json['reason'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class AuditEvent {
  const AuditEvent({
    required this.id,
    required this.actorId,
    required this.resource,
    required this.resourceId,
    required this.action,
    required this.createdAt,
    this.churchId,
    this.previousValues,
    this.newValues,
    this.reason,
  });

  final String id;
  final String actorId;
  final String resource;
  final String resourceId;
  final String action;
  final String? churchId;
  final Map<String, dynamic>? previousValues;
  final Map<String, dynamic>? newValues;
  final String? reason;
  final DateTime createdAt;

  factory AuditEvent.fromJson(Map<String, dynamic> json) => AuditEvent(
        id: json['id'] as String,
        actorId: json['actor_id'] as String,
        resource: json['resource'] as String,
        resourceId: json['resource_id'] as String,
        action: json['action'] as String,
        churchId: json['church_id'] as String?,
        previousValues: json['previous_values'] as Map<String, dynamic>?,
        newValues: json['new_values'] as Map<String, dynamic>?,
        reason: json['reason'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class RankingEntry {
  const RankingEntry({
    required this.leaderId,
    required this.leaderName,
    required this.completedVisits,
    required this.position,
  });

  final String leaderId;
  final String leaderName;
  final int completedVisits;
  final int position;

  factory RankingEntry.fromJson(Map<String, dynamic> json) => RankingEntry(
        leaderId: json['leader_id'] as String,
        leaderName: json['leader_name'] as String,
        completedVisits: json['completed_visits'] as int,
        position: json['position'] as int,
      );
}
