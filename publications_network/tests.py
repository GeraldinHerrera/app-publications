from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import SocialAccount, PostContent, PostTask

class PublicationsHistoryViewsTest(TestCase):
    def setUp(self):
        self.account = SocialAccount.objects.create(
            platform='instagram',
            account_user='usuario_test',
            account_password='secret_password'
        )
        self.post = PostContent.objects.create(
            file='publications_media/test.jpg',
            caption='Mi primera publicación de prueba',
            post_type='post'
        )
        self.task = PostTask.objects.create(
            post_content=self.post,
            account=self.account,
            scheduled_at=timezone.now(),
            status='pending'
        )

    def test_index_historial_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Historial de Publicaciones')
        self.assertContains(response, 'usuario_test')
        self.assertContains(response, 'Instagram')
        self.assertContains(response, 'Mi primera publicación de prueba')
        self.assertContains(response, 'Ver detalle')

    def test_post_detail_view(self):
        response = self.client.get(reverse('post_detail', args=[self.post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Detalle de la Publicación #{self.post.id}')
        self.assertContains(response, 'Mi primera publicación de prueba')
        self.assertContains(response, 'usuario_test')

    @patch('publications_network.views.send_alert_notification')
    def test_create_publication_view(self, mock_send_alert):
        mock_send_alert.return_value = True

        data = {
            'account_mode': 'new',
            'new_platform': 'tiktok',
            'new_account_user': 'user_tiktok_test',
            'post_mode': 'new',
            'new_caption': 'Nueva publicación desde el test',
            'status': 'completed',
            'recipient_email': 'hgeraldin35@gmail.com'
        }
        response = self.client.post(reverse('create_publication'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'guardada')

        # Verificar que la tarea quedó grabada como 'completed'
        task = PostTask.objects.filter(account__account_user='user_tiktok_test').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.status, 'completed')
        self.assertTrue(mock_send_alert.called)

    @patch('publications_network.views.generate_ai_response')
    def test_ai_assistant_view(self, mock_generate_ai):
        mock_generate_ai.return_value = 'Respuesta simulada de la IA Gemini'

        # Test GET
        response_get = self.client.get(reverse('ai_assistant'))
        self.assertEqual(response_get.status_code, 200)
        self.assertContains(response_get, 'Asistente de IA')

        # Test POST
        response_post = self.client.post(reverse('ai_assistant'), {'prompt': '¿Cuáles son las tendencias?'})
        self.assertEqual(response_post.status_code, 200)
        self.assertContains(response_post, 'Respuesta simulada de la IA Gemini')
        self.assertTrue(mock_generate_ai.called)
