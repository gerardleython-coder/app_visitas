import 'package:timezone/data/latest.dart' as timezone_data;
import 'package:timezone/timezone.dart' as timezone;

abstract final class BogotaTime {
  static const name = 'America/Bogota';
  static timezone.Location? _location;

  static void initialize() {
    timezone_data.initializeTimeZones();
    _location = timezone.getLocation(name);
  }

  static timezone.Location get _bogota =>
      _location ?? (throw StateError('BogotaTime.initialize() must run first'));

  static DateTime now() => timezone.TZDateTime.now(_bogota);

  static DateTime display(DateTime instant) =>
      timezone.TZDateTime.from(instant.toUtc(), _bogota);

  static DateTime wallClockToUtc({
    required int year,
    required int month,
    required int day,
    required int hour,
    required int minute,
  }) =>
      timezone.TZDateTime(_bogota, year, month, day, hour, minute).toUtc();
}
