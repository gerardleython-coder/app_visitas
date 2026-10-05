import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app/app_visitas_app.dart';
import 'core/time/bogota_time.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('es_CO');
  BogotaTime.initialize();
  runApp(const AppVisitasApp());
}
