"""
Tests para la resolución de tablas por ID y nombre
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from noco_core.client import NocoClient
from noco_core.table import NocoTable
from noco_core.result import NocoResult


class TestTableResolution:
    """Tests para la resolución de tablas"""

    def test_resuelve_por_id_directo(self):
        """Cuando se pasa un ID válido, lo resuelve directamente"""
        client = NocoClient("https://test.com", "token", "base123")
        
        mock_meta = Mock(spec=NocoResult)
        mock_meta.success = True
        mock_meta.data = {"title": "MiTabla", "id": "mbnzpnp57fi1woh"}
        mock_meta.errors = []
        
        with patch.object(client, 'get_table_meta', return_value=mock_meta):
            table = client.table("mbnzpnp57fi1woh")
            
            assert table.table_id == "mbnzpnp57fi1woh"
            assert table.name == "MiTabla"
            assert table.resolution_error is None
            assert not table.is_unresolved()

    def test_resuelve_por_nombre_cuando_id_falla(self):
        """Cuando el ID falla, intenta resolver por nombre"""
        client = NocoClient("https://test.com", "token", "base123")
        
        mock_meta_fail = Mock(spec=NocoResult)
        mock_meta_fail.success = False
        mock_meta_fail.data = None
        mock_meta_fail.errors = ["No encontrado"]
        
        mock_lookup = Mock(spec=NocoResult)
        mock_lookup.success = True
        mock_lookup.data = {"id": "mbnzpnp57fi1woh", "title": "Clientes"}
        mock_lookup.errors = []
        
        with patch.object(client, 'get_table_meta', return_value=mock_meta_fail):
            with patch.object(client, 'find_table_id_by_name', return_value=mock_lookup):
                table = client.table("Clientes")
                
                assert table.table_id == "mbnzpnp57fi1woh"
                assert table.name == "Clientes"
                assert table.resolution_error is None

    def test_no_resuelve_y_no_lanza_excepcion(self):
        """Cuando ambas estrategias fallan, NO lanza excepción"""
        client = NocoClient("https://test.com", "token", "base123")
        
        mock_meta_fail = Mock(spec=NocoResult)
        mock_meta_fail.success = False
        mock_meta_fail.data = None
        mock_meta_fail.errors = ["ID no encontrado"]
        
        mock_lookup_fail = Mock(spec=NocoResult)
        mock_lookup_fail.success = False
        mock_lookup_fail.data = None
        mock_lookup_fail.errors = ["Nombre no encontrado"]
        
        with patch.object(client, 'get_table_meta', return_value=mock_meta_fail):
            with patch.object(client, 'find_table_id_by_name', return_value=mock_lookup_fail):
                # Esto NO debe lanzar excepción
                table = client.table("TablaInexistente")
                
                assert table.table_id is None
                assert table.name == "TablaInexistente"
                assert table.resolution_error is not None
                assert "TablaInexistente" in table.resolution_error
                assert table.is_unresolved()

    def test_metodos_devuelven_fail_cuando_no_resuelto(self):
        """Todos los métodos devuelven NocoResult.fail cuando table_id es None"""
        client = NocoClient("https://test.com", "token", "base123")
        
        table = NocoTable(
            client=client,
            table_id=None,
            name="TablaNoResuelta",
            resolution_error="No se pudo resolver"
        )
        
        # Probar cada método
        result_meta = table.meta()
        assert isinstance(result_meta, NocoResult)
        assert result_meta.success is False
        assert "TablaNoResuelta" in result_meta.errors[0]
        
        result_read = table.read()
        assert isinstance(result_read, NocoResult)
        assert result_read.success is False
        
        result_create = table.create({"campo": "valor"})
        assert isinstance(result_create, NocoResult)
        assert result_create.success is False
        
        result_update = table.update("rec123", {"campo": "nuevo"})
        assert isinstance(result_update, NocoResult)
        assert result_update.success is False
        
        result_delete = table.delete("rec123")
        assert isinstance(result_delete, NocoResult)
        assert result_delete.success is False

    def test_repr_muestra_estado_no_resuelto(self):
        """__repr__ indica claramente si la tabla está no resuelta"""
        client = NocoClient("https://test.com", "token", "base123")
        
        # Tabla resuelta
        table_ok = NocoTable(client=client, table_id="mbnzpnp57fi1woh", name="Clientes")
        repr_ok = repr(table_ok)
        assert "Clientes" in repr_ok
        assert "UNRESOLVED" not in repr_ok
        
        # Tabla no resuelta
        table_fail = NocoTable(
            client=client,
            table_id=None,
            name="Fallida",
            resolution_error="Error de resolución"
        )
        repr_fail = repr(table_fail)
        assert "Fallida" in repr_fail
        assert "UNRESOLVED" in repr_fail
        assert "Error de resolución" in repr_fail


if __name__ == "__main__":
    pytest.main([__file__, "-v"])